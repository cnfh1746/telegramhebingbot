import logging
import os
import shutil
import threading
from flask import Flask
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import config
import merger

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 临时存储用户数据 (实际生产中建议使用 Redis)
# 结构: {user_id: {'mode': 'album', 'files': ['path1', 'path2']}}
user_data = {}

# === 保活 Web Server ===
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive!", 200

def run_web_server():
    # 获取环境变量中的端口 (Koyeb/Render 会提供 PORT)
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
# =======================

def get_user_temp_dir(user_id):
    """获取用户的临时目录路径"""
    path = os.path.join(config.TEMP_DIR, str(user_id))
    if not os.path.exists(path):
        os.makedirs(path)
    return path

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """响应 /start 命令"""
    await update.message.reply_text(
        "👋 欢迎使用合并机器人！\n\n"
        "🛠 **使用说明**:\n"
        "1. **默认模式 (相册)**: 发送 /album 切换回此模式。直接发送多张图片，打包发送。\n"
        "2. **拼接模式**: 发送 /vertical (垂直) 或 /horizontal (水平) 切换到长图拼接。\n"
        "3. 发送 /end 结束并开始处理。\n"
        "4. 发送 /clear 清空队列。"
    )

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置合并模式"""
    mode = update.message.text.replace('/', '')
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {'mode': 'album', 'files': []}
    
    user_data[user_id]['mode'] = mode
    await update.message.reply_text(f"✅ 模式已切换为: {mode}")

async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清空队列"""
    user_id = update.effective_user.id
    temp_dir = get_user_temp_dir(user_id)
    
    # 删除物理文件
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
    
    # 重置数据
    if user_id in user_data:
        user_data[user_id]['files'] = []
    
    await update.message.reply_text("🗑️ 队列已清空。")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收并下载媒体文件"""
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {'mode': 'album', 'files': []}
    
    # 获取文件对象
    if update.message.photo:
        # 图片取最高画质
        file_obj = await update.message.photo[-1].get_file()
        ext = '.jpg'
    elif update.message.video:
        file_obj = await update.message.video.get_file()
        ext = '.mp4'
    elif update.message.document:
        # 支持以文件形式发送的图片/视频
        file_obj = await update.message.document.get_file()
        fname = update.message.document.file_name
        ext = os.path.splitext(fname)[1] if fname else '.dat'
    else:
        return

    # 准备保存路径
    temp_dir = get_user_temp_dir(user_id)
    # 使用 file_unique_id 防止文件名冲突
    file_path = os.path.join(temp_dir, f"{file_obj.file_unique_id}{ext}")
    
    # 下载文件
    await file_obj.download_to_drive(file_path)
    
    user_data[user_id]['files'].append(file_path)
    
    count = len(user_data[user_id]['files'])
    await update.message.reply_text(f"📥 已接收第 {count} 个文件。发送 /end 开始合并。")

async def merge_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """响应 /end 命令，执行合并"""
    user_id = update.effective_user.id
    
    if user_id not in user_data or not user_data[user_id].get('files'):
        await update.message.reply_text("⚠️ 你还没有发送任何文件。")
        return

    files = user_data[user_id]['files']
    mode = user_data[user_id]['mode']
    
    await update.message.reply_text(f"⏳ 正在处理 {len(files)} 个文件，请稍候...")
    
    try:
        if mode == 'album':
            # 相册模式：直接发送 Media Group
            media_group = []
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    media_group.append(InputMediaPhoto(open(f, 'rb')))
                elif f.lower().endswith(('.mp4', '.mov', '.avi')):
                    media_group.append(InputMediaVideo(open(f, 'rb')))
            
            # 分批发送，每批最多 10 个
            for i in range(0, len(media_group), 10):
                chunk = media_group[i:i+10]
                await update.message.reply_media_group(media=chunk)
            
            await update.message.reply_text("✅ 发送完成！")
            
        else:
            # 拼接模式：调用 merger
            output_path = merger.process_media(files, mode)
            
            if output_path and os.path.exists(output_path):
                await update.message.reply_text("✅ 拼接成功，正在上传...")
                if output_path.endswith('.mp4'):
                    await update.message.reply_video(output_path)
                else:
                    await update.message.reply_photo(output_path)
            else:
                await update.message.reply_text("❌ 合并失败，可能是文件格式不支持或损坏。")
            
    except Exception as e:
        logging.error(f"Merge error: {e}")
        await update.message.reply_text(f"❌ 处理出错: {str(e)}")
        
    finally:
        # 清理：完成合并后，清空队列和临时文件
        # 实际使用中，可能希望保留一会，这里默认清理
        temp_dir = get_user_temp_dir(user_id)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        user_data[user_id]['files'] = []

if __name__ == '__main__':
    # 检查 Token
    if not config.BOT_TOKEN or "TOKEN" in config.BOT_TOKEN and len(config.BOT_TOKEN) < 20:
        print("🔴 错误: 请在 config.py 中配置正确的 BOT_TOKEN！")
        exit(1)

    # 确保根临时目录存在
    if not os.path.exists(config.TEMP_DIR):
        os.makedirs(config.TEMP_DIR)

    # 启动 Web Server 用于保活
    threading.Thread(target=run_web_server, daemon=True).start()

    application = ApplicationBuilder().token(config.BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler(['vertical', 'horizontal', 'long', 'album'], set_mode))
    application.add_handler(CommandHandler('end', merge_media))
    application.add_handler(CommandHandler('clear', clear_queue))
    # 处理图片、视频、文档
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))
    
    print(f"🤖 机器人已启动 (Token: {config.BOT_TOKEN[:5]}...)")
    application.run_polling()
