from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QSpinBox,
                             QComboBox, QGroupBox, QScrollArea, QFrame)
from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from core.image_processor import ImageProcessor
from utils.file_handler import FileHandler
import os
from PIL import Image
import cv2

class ImageLabel(QLabel):
    # 添加选择完成的信号
    selection_changed = Signal(QRect)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection = None
        self.start_pos = None
        self.current_image = None
        self.scale_factor = 1.0
        self.setMinimumSize(400, 300)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #ccc;")
        
    def set_image(self, image_path):
        """设置显示的图片"""
        try:
            # 使用PIL读取图片
            image = Image.open(image_path)
            # 转换为RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            # 保存原始图片尺寸
            self.original_size = image.size
            # 缩放图片以适应标签大小
            scaled_image = self.scale_image(image)
            # 转换为QPixmap并显示
            self.set_image_from_array(scaled_image)
            self.current_image = image_path
            # 清除选择区域
            self.selection = None
            self.update()
        except Exception as e:
            print(f"加载图片失败: {str(e)}")
            
    def set_image_from_array(self, pil_image):
        """从PIL图片设置显示内容"""
        try:
            # 转换为RGB模式
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            # 转换为QImage
            data = pil_image.tobytes("raw", "RGB")
            qimage = QImage(
                data, pil_image.size[0], pil_image.size[1],
                pil_image.size[0] * 3, QImage.Format_RGB888
            )
            # 转换为QPixmap并显示
            self.setPixmap(QPixmap.fromImage(qimage))
        except Exception as e:
            print(f"设置图片失败: {str(e)}")
            
    def scale_image(self, image):
        """缩放图片以适应标签大小"""
        # 获取标签尺寸
        label_size = self.size()
        # 计算缩放比例
        width_ratio = label_size.width() / image.size[0]
        height_ratio = label_size.height() / image.size[1]
        # 使用较小的比例以保持宽高比
        self.scale_factor = min(width_ratio, height_ratio)
        # 计算新尺寸
        new_size = (
            int(image.size[0] * self.scale_factor),
            int(image.size[1] * self.scale_factor)
        )
        # 缩放图片
        return image.resize(new_size, Image.Resampling.LANCZOS)
        
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton and self.pixmap():
            # 记录起始位置
            self.start_pos = event.pos()
            # 清除选择区域
            self.selection = None
            self.update()
            
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.start_pos and self.pixmap():
            # 计算选择区域
            self.selection = QRect(
                self.start_pos,
                event.pos()
            ).normalized()
            self.update()
            
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.pixmap():
            # 完成选择
            self.selection = QRect(
                self.start_pos,
                event.pos()
            ).normalized()
            self.start_pos = None
            self.update()
            
    def paintEvent(self, event):
        """绘制事件"""
        super().paintEvent(event)
        if self.selection and self.pixmap():
            # 绘制选择区域
            painter = QPainter(self)
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            painter.drawRect(self.selection)
            
    def get_scaled_rect(self):
        """获取缩放后的选择区域（相对原始图片）"""
        if not self.selection or not self.pixmap():
            return None
            
        # 获取图片在标签中的位置
        pixmap_rect = self.get_pixmap_rect()
        if not pixmap_rect:
            return None
            
        # 计算选择区域相对于图片的位置
        x = (self.selection.x() - pixmap_rect.x()) / self.scale_factor
        y = (self.selection.y() - pixmap_rect.y()) / self.scale_factor
        w = self.selection.width() / self.scale_factor
        h = self.selection.height() / self.scale_factor
        
        # 确保坐标在有效范围内
        x = max(0, min(x, self.original_size[0]))
        y = max(0, min(y, self.original_size[1]))
        w = min(w, self.original_size[0] - x)
        h = min(h, self.original_size[1] - y)
        
        return QRect(int(x), int(y), int(w), int(h))
        
    def get_pixmap_rect(self):
        """获取图片在标签中的位置"""
        if not self.pixmap():
            return None
            
        # 计算图片在标签中的位置（居中对齐）
        pixmap_size = self.pixmap().size()
        label_size = self.size()
        x = (label_size.width() - pixmap_size.width()) // 2
        y = (label_size.height() - pixmap_size.height()) // 2
        
        return QRect(x, y, pixmap_size.width(), pixmap_size.height())

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_processor = ImageProcessor()
        self.selected_files = []
        self.current_image = None
        self.video_window = None
        
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("批量去水印工具")
        self.setMinimumSize(1200, 800)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        layout = QHBoxLayout(main_widget)
        
        # 创建预览区域
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        
        # 添加预览标签
        self.image_label = ImageLabel()
        preview_layout.addWidget(self.image_label)
        
        # 添加预览区域到主布局
        layout.addWidget(preview_widget, stretch=2)
        
        # 创建控制面板
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel, stretch=1)
        
    def _create_control_panel(self):
        """创建控制面板"""
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setSpacing(10)
        control_panel.setFixedWidth(300)
        control_panel.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QPushButton {
                padding: 8px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        
        # 添加标题标签
        title_label = QLabel("批量去水印处理工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1565C0;
            padding: 10px;
            margin: 10px;
        """)
        control_layout.addWidget(title_label)
        
        # 添加模式切换组
        mode_group = QGroupBox("处理模式")
        mode_layout = QHBoxLayout()
        
        self.image_mode_btn = QPushButton("图片模式")
        self.image_mode_btn.setEnabled(False)
        mode_layout.addWidget(self.image_mode_btn)
        
        self.video_mode_btn = QPushButton("视频模式")
        self.video_mode_btn.clicked.connect(self.switch_to_video_mode)
        mode_layout.addWidget(self.video_mode_btn)
        
        mode_group.setLayout(mode_layout)
        control_layout.addWidget(mode_group)
        
        # 创建文件选择区域
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(10)
        
        # 添加选择文件按钮
        select_button = QPushButton("选择文件")
        select_button.clicked.connect(self.select_files)
        file_layout.addWidget(select_button)
        
        # 添加选择文件夹按钮
        select_folder_button = QPushButton("选择文件夹")
        select_folder_button.clicked.connect(self.select_folder)
        file_layout.addWidget(select_folder_button)
        
        # 添加状态标签
        self.status_label = QLabel("请选择要处理的文件或文件夹")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            padding: 10px;
            color: #666666;
        """)
        file_layout.addWidget(self.status_label)
        
        file_group.setLayout(file_layout)
        control_layout.addWidget(file_group)
        
        # 创建水印处理设置区域
        process_group = QGroupBox("处理设置")
        process_layout = QVBoxLayout()
        process_layout.setSpacing(10)
        
        # 添加处理方法选择
        method_layout = QHBoxLayout()
        method_label = QLabel("处理方法:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Telea", "Navier-Stokes"])
        self.method_combo.currentTextChanged.connect(self.update_method)
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.method_combo)
        process_layout.addLayout(method_layout)
        
        # 添加修复半径设置
        radius_layout = QHBoxLayout()
        radius_label = QLabel("修复半径:")
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(1, 10)
        self.radius_spin.setValue(3)
        self.radius_spin.valueChanged.connect(self.update_radius)
        radius_layout.addWidget(radius_label)
        radius_layout.addWidget(self.radius_spin)
        process_layout.addLayout(radius_layout)
        
        process_group.setLayout(process_layout)
        control_layout.addWidget(process_group)
        
        # 添加操作按钮
        self.detect_button = QPushButton("自动检测水印")
        self.detect_button.clicked.connect(self.detect_watermark)
        self.detect_button.setEnabled(False)
        control_layout.addWidget(self.detect_button)
        
        self.preview_button = QPushButton("预览效果")
        self.preview_button.clicked.connect(self.preview_removal)
        self.preview_button.setEnabled(False)
        control_layout.addWidget(self.preview_button)
        
        self.process_button = QPushButton("开始处理")
        self.process_button.clicked.connect(self.process_files)
        self.process_button.setEnabled(False)
        control_layout.addWidget(self.process_button)
        
        # 添加弹簧
        control_layout.addStretch()
        
        return control_panel
        
    def switch_to_video_mode(self):
        """切换到视频模式"""
        from ui.video_window import VideoWindow
        self.video_window = VideoWindow()
        self.video_window.show()
        self.hide()
        
    def select_files(self):
        """选择要处理的文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片文件",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件 (*.*)"
        )
        
        if files:
            self.selected_files = files
            # 加载第一张图片进行预览
            self.load_image(files[0])
            # 更新状态
            self.status_label.setText(f"已选择 {len(files)} 个文件")
            
    def select_folder(self):
        """选择要处理的文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择图片文件夹",
            ""
        )
        
        if folder:
            # 扫描文件夹
            image_files, _ = FileHandler.scan_directory(folder)
            if image_files:
                self.selected_files = image_files
                # 加载第一张图片进行预览
                self.load_image(image_files[0])
                # 更新状态
                self.status_label.setText(f"已选择 {len(image_files)} 个文件")
            else:
                self.status_label.setText("所选文件夹中没有图片文件")
                
    def load_image(self, image_path):
        """加载并显示图片"""
        try:
            # 设置当前图片路径
            self.current_image = image_path
            # 在预览区域显示图片
            self.image_label.set_image(image_path)
            # 更新状态
            self.status_label.setText(f"已加载图片: {os.path.basename(image_path)}")
            # 启用相关按钮
            self.detect_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.process_button.setEnabled(True)
        except Exception as e:
            self.status_label.setText(f"加载图片失败: {str(e)}")
            
    def update_method(self, method):
        """更新处理方法"""
        self.image_processor.method = 'telea' if method == 'Telea' else 'ns'
        if self.image_label.selection:
            self.preview_removal()
        
    def update_radius(self, value):
        """更新修复半径"""
        self.image_processor.inpaint_radius = value
        if self.image_label.selection:
            self.preview_removal()
        
    def detect_watermark(self):
        """自动检测水印"""
        if not self.current_image:
            return
            
        try:
            self.status_label.setText("正在检测水印区域...")
            # 禁用按钮
            self.detect_button.setEnabled(False)
            self.preview_button.setEnabled(False)
            self.process_button.setEnabled(False)
            
            # 检测水印区域
            region = self.image_processor.auto_detect_watermark(self.current_image)
            if region:
                x, y, w, h = region
                # 获取图片在标签中的位置
                pixmap_rect = self.image_label.get_pixmap_rect()
                if pixmap_rect:
                    # 计算缩放比例
                    scale_x = pixmap_rect.width() / self.image_label.original_size[0]
                    scale_y = pixmap_rect.height() / self.image_label.original_size[1]
                    
                    # 转换为显示坐标
                    display_x = int(x * scale_x) + pixmap_rect.x()
                    display_y = int(y * scale_y) + pixmap_rect.y()
                    display_w = int(w * scale_x)
                    display_h = int(h * scale_y)
                    
                    # 设置选择区域
                    self.image_label.selection = QRect(
                        display_x, display_y, display_w, display_h
                    )
                    self.image_label.update()
                    
                    # 更新状态
                    self.status_label.setText("已检测到水印区域")
                    self.preview_button.setEnabled(True)
                    self.process_button.setEnabled(True)
                    
                    # 自动预览效果
                    self.preview_removal()
            else:
                self.status_label.setText("未检测到水印区域")
        except Exception as e:
            self.status_label.setText(f"检测失败: {str(e)}")
        finally:
            # 重新启用按钮
            self.detect_button.setEnabled(True)
        
    def preview_removal(self):
        """预览去水印效果"""
        if not self.current_image or not self.image_label.selection:
            return
            
        try:
            # 获取选择区域（转换到原始图片坐标）
            scaled_rect = self.image_label.get_scaled_rect()
            if not scaled_rect:
                return
                
            self.image_processor.set_watermark_region(
                scaled_rect.x(), scaled_rect.y(),
                scaled_rect.width(), scaled_rect.height()
            )
            
            # 预览效果
            result = self.image_processor.preview_removal(self.current_image)
            
            # 转换为PIL图片
            result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(result_rgb)
            
            # 显示处理后的图片
            self.image_label.set_image_from_array(pil_image)
            
        except Exception as e:
            self.status_label.setText(f"预览失败: {str(e)}")
            
    def process_files(self):
        """处理所有选中的文件"""
        if not self.selected_files or not self.image_label.selection:
            return
            
        # 获取选择区域（转换到原始图片坐标）
        scaled_rect = self.image_label.get_scaled_rect()
        if not scaled_rect:
            return
            
        # 设置水印区域
        self.image_processor.set_watermark_region(
            scaled_rect.x(), scaled_rect.y(),
            scaled_rect.width(), scaled_rect.height()
        )
        
        # 禁用所有按钮
        self.detect_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.process_button.setEnabled(False)
        
        processed_count = 0
        total_files = len(self.selected_files)
        output_dir = None
        
        try:
            # 显示开始处理的消
            self.status_label.setText(f"开始处理 {total_files} 个文件...")
            
            for file_path in self.selected_files:
                if FileHandler.is_image(file_path):
                    try:
                        # 更新当前处理的文件名
                        current_file = os.path.basename(file_path)
                        self.status_label.setText(f"正在处理: {current_file} ({processed_count + 1}/{total_files})")
                        
                        # 生成输出路径
                        output_path = FileHandler.get_output_path(file_path)
                        if output_dir is None:
                            output_dir = os.path.dirname(output_path)
                            
                        # 处理图片
                        self.image_processor.remove_watermark(file_path, output_path)
                        processed_count += 1
                        
                    except Exception as e:
                        self.status_label.setText(f"处理失败: {current_file} - {str(e)}")
                        continue
                        
            # 处理完成后的提示
            if output_dir and processed_count > 0:
                success_message = (
                    f"处理完成！\n"
                    f"成功处理 {processed_count}/{total_files} 个文件\n"
                    f"文件保存在: {output_dir}"
                )
                self.status_label.setText(success_message)
                
                # 在资源管理器中打开输出目录
                try:
                    os.startfile(output_dir)
                except Exception:
                    pass  # 忽略打开目录失败的错误
            else:
                self.status_label.setText("处理失败：没有成功处理任何文件")
                
        except Exception as e:
            self.status_label.setText(f"批量处理失败: {str(e)}")
            
        finally:
            # 重新启用按钮
            self.detect_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.process_button.setEnabled(True)