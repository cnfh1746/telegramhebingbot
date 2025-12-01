import os
from PIL import Image
from moviepy.editor import VideoFileClip, concatenate_videoclips, clips_array

def process_media(file_paths, mode='vertical'):
    """
    根据文件类型选择合并逻辑
    """
    if not file_paths:
        return None
    
    # 简单的类型检测 (基于扩展名)
    first_file = file_paths[0].lower()
    if first_file.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return merge_images(file_paths, mode)
    elif first_file.endswith(('.mp4', '.mov', '.avi')):
        return merge_videos(file_paths, mode)
    else:
        return None

def merge_images(file_paths, mode='vertical'):
    images = []
    for p in file_paths:
        try:
            images.append(Image.open(p))
        except Exception as e:
            print(f"Error opening image {p}: {e}")
            continue
    
    if not images:
        return None

    widths, heights = zip(*(i.size for i in images))

    if mode == 'horizontal':
        total_width = sum(widths)
        max_height = max(heights)
        new_im = Image.new('RGB', (total_width, max_height), (255, 255, 255))
        x_offset = 0
        for im in images:
            new_im.paste(im, (x_offset, 0))
            x_offset += im.size[0]
    else: # vertical or long
        max_width = max(widths)
        total_height = sum(heights)
        new_im = Image.new('RGB', (max_width, total_height), (255, 255, 255))
        y_offset = 0
        for im in images:
            # 居中对齐? 暂时左对齐
            new_im.paste(im, (0, y_offset))
            y_offset += im.size[1]

    # 保存到和第一个文件相同的目录
    output_dir = os.path.dirname(file_paths[0])
    output_path = os.path.join(output_dir, "merged_result.jpg")
    new_im.save(output_path)
    return output_path

def merge_videos(file_paths, mode='vertical'):
    try:
        clips = [VideoFileClip(p) for p in file_paths]
        
        # 视频默认是时间轴拼接 (concatenate)
        # 如果用户非要 vertical/horizontal 布局拼接，moviepy 的 clips_array 可以做到
        # 但这通常会导致分辨率问题。这里我们假设视频是按时间顺序拼接。
        # 如果要支持空间拼接：
        if mode in ['vertical', 'horizontal']:
             # 简单的空间拼接逻辑 (仅作演示，可能需要调整分辨率一致)
             # vertical: [[clip1], [clip2]]
             # horizontal: [[clip1, clip2]]
             # 但考虑到视频长宽比各异，直接拼接会很丑。
             # 这里默认只做时间拼接，除非用户明确想要画中画效果。
             # 为了稳健性，我们暂时只做时间维度的拼接。
             pass

        final_clip = concatenate_videoclips(clips, method="compose")
        
        output_dir = os.path.dirname(file_paths[0])
        output_path = os.path.join(output_dir, "merged_result.mp4")
        
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
        
        # 关闭 clips 释放资源
        for clip in clips:
            clip.close()
            
        return output_path
    except Exception as e:
        print(f"Video merge error: {e}")
        return None
