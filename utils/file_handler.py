import os
from typing import List, Tuple

class FileHandler:
    # 支持的图片格式
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
    # 支持的视频格式
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv'}
    
    @classmethod
    def is_image(cls, file_path: str) -> bool:
        """判断文件是否为图片"""
        return os.path.splitext(file_path)[1].lower() in cls.IMAGE_EXTENSIONS
    
    @classmethod
    def is_video(cls, file_path: str) -> bool:
        """判断文件是否为视频"""
        return os.path.splitext(file_path)[1].lower() in cls.VIDEO_EXTENSIONS
    
    @classmethod
    def scan_directory(cls, directory: str) -> Tuple[List[str], List[str]]:
        """扫描目录，返回图片和视频文件列表"""
        image_files = []
        video_files = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if cls.is_image(file_path):
                    image_files.append(file_path)
                elif cls.is_video(file_path):
                    video_files.append(file_path)
                    
        return image_files, video_files
    
    @classmethod
    def get_output_path(cls, input_path: str, suffix: str = "_nowm") -> str:
        """生成输出文件路径"""
        # 获取文件所在目录
        input_dir = os.path.dirname(input_path)
        # 创建processed子目录
        output_dir = os.path.join(input_dir, "processed")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # 获取文件名和扩展名
        filename, ext = os.path.splitext(os.path.basename(input_path))
        # 生成新文件名
        new_filename = f"{filename}{suffix}{ext}"
        # 返回完整的输出路径
        return os.path.join(output_dir, new_filename)
    
    @classmethod
    def ensure_directory(cls, directory: str) -> None:
        """确保目录存在，如果不存在则创建"""
        if not os.path.exists(directory):
            os.makedirs(directory) 