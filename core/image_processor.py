import cv2
import numpy as np
from PIL import Image
import os
from typing import Callable, Optional

class ImageProcessor:
    def __init__(self):
        self.watermark_region = None  # 水印区域 (x, y, width, height)
        self.inpaint_radius = 3       # 修复算法的半径参数
        self.method = 'telea'         # 'telea' 或 'ns' (Navier-Stokes)
        
    def set_watermark_region(self, x, y, width, height):
        """设置水印区域"""
        self.watermark_region = (x, y, width, height)
        
    def read_image(self, path: str) -> np.ndarray:
        """读取图片"""
        # 使用PIL读取图片
        try:
            pil_image = Image.open(path)
            # 转换为RGB模式
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            # 转换为numpy数组
            image = np.array(pil_image)
            # 转换为BGR格式（OpenCV格式）
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            return image
        except Exception as e:
            print(f"读取图片失败: {path} - {str(e)}")
            return None
            
    def save_image(self, path: str, image: np.ndarray) -> None:
        """保存图片"""
        try:
            # 转换为RGB格式
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            # 转换为PIL图片
            pil_image = Image.fromarray(image_rgb)
            # 保存图片
            pil_image.save(path, quality=95)
        except Exception as e:
            raise ValueError(f"无法保存图片: {path} - {str(e)}")
        
    def remove_watermark(self, input_path: str, output_path: str) -> None:
        """移除水印"""
        if not self.watermark_region:
            raise ValueError("请先设置水印区域")
            
        # 读取图片
        image = self.read_image(input_path)
        if image is None:
            raise ValueError(f"无法读取图片: {input_path}")
            
        # 创建掩码
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        x, y, w, h = self.watermark_region
        mask[y:y+h, x:x+w] = 255
        
        # 使用修复算法移除水印
        radius = self.inpaint_radius
        result = cv2.inpaint(image, mask, radius, cv2.INPAINT_TELEA)
        
        # 保存结果
        self.save_image(output_path, result)
        
    def auto_detect_watermark(self, image_path):
        """自动检测水印区域"""
        # 读取图片
        image = self.read_image(image_path)
        if image is None:
            raise ValueError(f"无法读取图片: {image_path}")
            
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 使用自适应阈值处理
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 25, 5
        )
        
        # 使用形态学操作去除噪点
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return None
            
        # 过滤和合并轮廓
        valid_contours = []
        min_area = image.shape[0] * image.shape[1] * 0.001  # 最小面积阈值
        max_area = image.shape[0] * image.shape[1] * 0.2    # 最大面积阈值
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area < area < max_area:
                valid_contours.append(contour)
                
        if not valid_contours:
            return None
            
        # 如果有多个轮廓，选择最可能的水印区域
        if len(valid_contours) > 1:
            # 计算每个轮廓的特征
            contour_features = []
            for contour in valid_contours:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h != 0 else 0
                solidity = cv2.contourArea(contour) / (w * h) if w * h != 0 else 0
                center_y = y + h/2
                score = solidity * (1 - abs(0.5 - center_y/image.shape[0]))
                contour_features.append((contour, score))
            
            # 选择得分最高的轮廓
            best_contour = max(contour_features, key=lambda x: x[1])[0]
            x, y, w, h = cv2.boundingRect(best_contour)
            
            # 扩大检测区域
            padding = 5
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(image.shape[1] - x, w + 2*padding)
            h = min(image.shape[0] - y, h + 2*padding)
            
            return (x, y, w, h)
        else:
            # 只有一个轮廓时直接使用
            x, y, w, h = cv2.boundingRect(valid_contours[0])
            
            # 扩大检测区域
            padding = 5
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(image.shape[1] - x, w + 2*padding)
            h = min(image.shape[0] - y, h + 2*padding)
            
            return (x, y, w, h)
        
    def preview_removal(self, image_path):
        """预览去水印效果"""
        if self.watermark_region is None:
            raise ValueError("请先设置水印区域")
            
        # 读取图片
        image = self.read_image(image_path)
            
        # 创建掩码
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        x, y, w, h = self.watermark_region
        mask[y:y+h, x:x+w] = 255
        
        # 使用Inpainting算法去除水印
        if self.method == 'telea':
            result = cv2.inpaint(image, mask, self.inpaint_radius, cv2.INPAINT_TELEA)
        else:
            result = cv2.inpaint(image, mask, self.inpaint_radius, cv2.INPAINT_NS)
            
        return result