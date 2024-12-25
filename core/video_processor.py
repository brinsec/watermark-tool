import cv2
import numpy as np
from PIL import Image
import ffmpeg
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import threading

class VideoProcessor:
    def __init__(self):
        self.video_path = None
        self.cap = None
        self.total_frames = 0
        self.fps = 0
        self.width = 0
        self.height = 0
        self.watermark_region = None
        self.method = 'telea'
        self.inpaint_radius = 3
        self.max_workers = max(1, os.cpu_count() - 1)  # 保留一个CPU核心给UI
        
    def load_video(self, video_path):
        """加载视频文件"""
        try:
            self.video_path = video_path
            self.cap = cv2.VideoCapture(video_path)
            
            # 获取视频基本信息
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            return True
        except Exception as e:
            print(f"加载视频失败: {str(e)}")
            return False
            
    def get_frame(self, frame_idx):
        """获取指定帧"""
        if not self.cap:
            return None
            
        try:
            # 设置帧位置
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            
            if ret:
                return frame  # 返回BGR格式的帧
            return None
        except Exception as e:
            print(f"读取帧失败: {str(e)}")
            return None
            
    def get_preview_frame(self, frame_idx, max_size=800):
        """获取预览帧（缩放到合适大小）"""
        frame = self.get_frame(frame_idx)
        if frame is None:
            return None
            
        try:
            # 计算缩放比例
            h, w = frame.shape[:2]
            scale = min(max_size/w, max_size/h)
            
            if scale < 1:
                new_size = (int(w*scale), int(h*scale))
                frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
                
            # 转换为RGB格式用于显示
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return frame_rgb
            
        except Exception as e:
            print(f"处理预览帧失败: {str(e)}")
            return None
            
    def set_watermark_region(self, x, y, w, h):
        """设置水印区域"""
        self.watermark_region = (int(x), int(y), int(w), int(h))
        
    def process_frame(self, frame):
        """处理单帧"""
        if frame is None or self.watermark_region is None:
            return frame
            
        try:
            # 创建掩码
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            x, y, w, h = self.watermark_region
            mask[y:y+h, x:x+w] = 255
            
            # 应用图像修复
            if self.method == 'telea':
                result = cv2.inpaint(frame, mask, self.inpaint_radius, cv2.INPAINT_TELEA)
            else:
                result = cv2.inpaint(frame, mask, self.inpaint_radius, cv2.INPAINT_NS)
                
            return result
        except Exception as e:
            print(f"处理帧失败: {str(e)}")
            return frame
            
    def process_frame_batch(self, start_idx, frames, temp_dir):
        """处理一批帧"""
        results = []
        for i, frame in enumerate(frames):
            if frame is None:
                continue
            # 处理帧
            processed = self.process_frame(frame)
            # 保存帧
            frame_idx = start_idx + i
            frame_path = os.path.join(temp_dir, f"frame_{frame_idx:06d}.jpg")
            cv2.imwrite(frame_path, processed, [cv2.IMWRITE_JPEG_QUALITY, 95])
            results.append(frame_idx)
        return results

    def process_video(self, output_path, progress_callback=None):
        """处理整个视频"""
        if not self.video_path or not self.watermark_region:
            return False
            
        try:
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(output_path), "temp_frames")
            os.makedirs(temp_dir, exist_ok=True)
            
            # 打开输入视频
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                return False
            
            # 获取视频信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            current_frame = 0
            
            try:
                # 处理每一帧
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # 处理帧
                    processed = self.process_frame(frame)
                    
                    # 保存帧
                    frame_path = os.path.join(temp_dir, f"frame_{current_frame:06d}.jpg")
                    cv2.imwrite(frame_path, processed, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    
                    # 更新进度
                    current_frame += 1
                    if progress_callback:
                        progress = (current_frame / total_frames) * 100
                        if not progress_callback(progress):
                            return False
                        
                # 使用ffmpeg合成视频
                frame_pattern = os.path.join(temp_dir, "frame_%06d.jpg")
                stream = ffmpeg.input(frame_pattern, framerate=self.fps)
                stream = ffmpeg.output(
                    stream, 
                    output_path,
                    vcodec='libx264',
                    pix_fmt='yuv420p',
                    preset='veryfast',
                    crf=23,
                    acodec='copy'
                )
                ffmpeg.run(stream, overwrite_output=True)
                
                return True
                
            finally:
                # 清理临时文件
                for file in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except:
                        pass
                try:
                    os.rmdir(temp_dir)
                except:
                    pass
                
        except Exception as e:
            print(f"处理视频失败: {str(e)}")
            return False
        
        finally:
            if cap:
                cap.release()
 