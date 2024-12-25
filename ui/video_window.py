from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QSpinBox,
                             QComboBox, QGroupBox, QScrollArea, QFrame,
                             QSlider, QStyle, QProgressDialog, QApplication)
from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal, QTimer, QThread
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
import cv2
import os
from core.video_processor import VideoProcessor
from utils.file_handler import FileHandler

class VideoPreviewLabel(QLabel):
    selection_changed = Signal(QRect)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection = None
        self.start_pos = None
        self.current_frame = None
        self.scale_factor = 1.0
        self.setMinimumSize(800, 600)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #ccc;")
        
    def set_frame(self, frame):
        """设置显示的帧"""
        if frame is None:
            return
            
        try:
            # 转换为QImage
            height, width = frame.shape[:2]
            bytes_per_line = 3 * width
            qimage = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 设置显示
            self.setPixmap(QPixmap.fromImage(qimage))
            self.current_frame = frame
            
            # 清除选择区域
            self.selection = None
            self.update()
        except Exception as e:
            print(f"设置帧失败: {str(e)}")
            
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton and self.pixmap():
            self.start_pos = event.pos()
            self.selection = None
            self.update()
            
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.start_pos and self.pixmap():
            self.selection = QRect(self.start_pos, event.pos()).normalized()
            self.update()
            
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.pixmap():
            self.selection = QRect(self.start_pos, event.pos()).normalized()
            self.start_pos = None
            self.update()
            # 发送选择区域改变信号
            if self.selection and self.selection.isValid():
                self.selection_changed.emit(self.selection)
                
    def paintEvent(self, event):
        """绘制事件"""
        super().paintEvent(event)
        if self.selection and self.pixmap():
            painter = QPainter(self)
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            painter.drawRect(self.selection)
            
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
        
class ProcessThread(QThread):
    """视频处理线程"""
    progress_updated = Signal(float)  # 进度信号
    finished = Signal(bool, str)      # 完成信号，参数：是否成功，输出路径
    
    def __init__(self, video_processor, output_path):
        super().__init__()
        self.video_processor = video_processor
        self.output_path = output_path
        self._is_canceled = False
        
    def cancel(self):
        """取消处理"""
        self._is_canceled = True
        
    def run(self):
        """运行处理线程"""
        try:
            success = self.video_processor.process_video(
                self.output_path,
                lambda p: self.progress_updated.emit(p) if not self._is_canceled else False
            )
            if not self._is_canceled:
                self.finished.emit(success, self.output_path)
        except Exception as e:
            print(f"处理失败: {str(e)}")
            if not self._is_canceled:
                self.finished.emit(False, str(e))

class VideoWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, False)  # 防止窗口被自动删除
        self.video_processor = VideoProcessor()
        self.current_frame_idx = 0
        self.playing = False
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.next_frame)
        self.video_files = []  # 存储所有待处理的视频文件
        self.current_video_idx = -1  # 当前预览的视频索引
        self.image_window = None  # 保存图片模式窗口的引用
        self.process_thread = None  # 保存处理线程的引用
        
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("视频去水印")
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
        self.preview_label = VideoPreviewLabel()
        self.preview_label.selection_changed.connect(self.on_selection_changed)
        preview_layout.addWidget(self.preview_label)
        
        # 添加时间轴
        self.timeline = QSlider(Qt.Horizontal)
        self.timeline.setMinimum(0)
        self.timeline.setMaximum(0)
        self.timeline.valueChanged.connect(self.timeline_changed)
        preview_layout.addWidget(self.timeline)
        
        # 添加播放控制
        control_layout = QHBoxLayout()
        
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_play)
        control_layout.addWidget(self.play_button)
        
        self.frame_label = QLabel("0/0")
        control_layout.addWidget(self.frame_label)
        
        preview_layout.addLayout(control_layout)
        
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
        
        # 添加标题
        title_label = QLabel("视频去水印")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1565C0;
            padding: 10px;
        """)
        control_layout.addWidget(title_label)
        
        # 添加模式切换组
        mode_group = QGroupBox("处理模式")
        mode_layout = QHBoxLayout()
        
        self.image_mode_btn = QPushButton("图片模式")
        self.image_mode_btn.clicked.connect(self.switch_to_image_mode)
        mode_layout.addWidget(self.image_mode_btn)
        
        self.video_mode_btn = QPushButton("视频模式")
        self.video_mode_btn.setEnabled(False)
        mode_layout.addWidget(self.video_mode_btn)
        
        mode_group.setLayout(mode_layout)
        control_layout.addWidget(mode_group)
        
        # 添加文件选择组
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        
        select_button = QPushButton("选择视频")
        select_button.clicked.connect(self.select_videos)
        file_layout.addWidget(select_button)
        
        select_folder_button = QPushButton("选择文件夹")
        select_folder_button.clicked.connect(self.select_folder)
        file_layout.addWidget(select_folder_button)
        
        # 添加视频列表
        self.video_list = QComboBox()
        self.video_list.currentIndexChanged.connect(self.on_video_changed)
        file_layout.addWidget(self.video_list)
        
        self.status_label = QLabel("请选择要处理的视频文件")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignCenter)
        file_layout.addWidget(self.status_label)
        
        file_group.setLayout(file_layout)
        control_layout.addWidget(file_group)
        
        # 添加处理设置组
        process_group = QGroupBox("处理设置")
        process_layout = QVBoxLayout()
        
        # 添加算法选择
        method_layout = QHBoxLayout()
        method_label = QLabel("处理算法:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Telea", "Navier-Stokes"])
        self.method_combo.currentTextChanged.connect(self.update_method)
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.method_combo)
        process_layout.addLayout(method_layout)
        
        # 添加半径设置
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
        self.process_button.clicked.connect(self.process_video)
        self.process_button.setEnabled(False)
        control_layout.addWidget(self.process_button)
        
        # 添加弹簧
        control_layout.addStretch()
        
        return control_panel
        
    def select_videos(self):
        """选择多个视频文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.avi *.mkv)"
        )
        
        if files:
            self.add_video_files(files)
            
    def select_folder(self):
        """选择包含视频的文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择视频文件夹",
            ""
        )
        
        if folder:
            # 扫描文件夹中的视频文件
            video_files = []
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.mp4', '.avi', '.mkv')):
                        video_files.append(os.path.join(root, file))
            
            if video_files:
                self.add_video_files(video_files)
            else:
                self.status_label.setText("所选文件夹中没有视频文件")
                
    def add_video_files(self, files):
        """添加视频文件到列表"""
        self.video_files = files
        self.video_list.clear()
        for file in files:
            self.video_list.addItem(os.path.basename(file))
            
        self.status_label.setText(f"已选择 {len(files)} 个视频文件")
        if files:
            self.video_list.setCurrentIndex(0)
            
    def on_video_changed(self, index):
        """视频切换处理"""
        if index >= 0 and index < len(self.video_files):
            self.current_video_idx = index
            self.load_video(self.video_files[index])
            
    def load_video(self, video_path):
        """加载视频文件"""
        if self.video_processor.load_video(video_path):
            self.current_frame_idx = 0
            self.timeline.setMaximum(self.video_processor.total_frames - 1)
            self.update_frame()
            self.status_label.setText(f"已加载视频: {os.path.basename(video_path)}")
            self.detect_button.setEnabled(True)
        else:
            self.status_label.setText("加载视频失败")
            
    def update_frame(self):
        """更新当前帧显示"""
        frame = self.video_processor.get_preview_frame(self.current_frame_idx)
        if frame is not None:
            self.preview_label.set_frame(frame)
            self.frame_label.setText(f"{self.current_frame_idx + 1}/{self.video_processor.total_frames}")
            self.timeline.setValue(self.current_frame_idx)
            
    def timeline_changed(self, value):
        """时间轴值改变"""
        if value != self.current_frame_idx:
            self.current_frame_idx = value
            self.update_frame()
            
    def toggle_play(self):
        """切换播放状态"""
        self.playing = not self.playing
        if self.playing:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.play_timer.start(1000 // self.video_processor.fps)
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.play_timer.stop()
            
    def next_frame(self):
        """播放下一帧"""
        if self.current_frame_idx < self.video_processor.total_frames - 1:
            self.current_frame_idx += 1
            self.update_frame()
        else:
            self.playing = False
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.play_timer.stop()
            
    def update_method(self, method):
        """更新处理方法"""
        self.video_processor.method = 'telea' if method == 'Telea' else 'ns'
        
    def update_radius(self, value):
        """更新修复半径"""
        self.video_processor.inpaint_radius = value
        
    def detect_watermark(self):
        """自动检测水印"""
        if not self.video_processor.video_path:
            return
            
        try:
            self.status_label.setText("正在检测水印区域...")
            # 禁用按钮
            self.detect_button.setEnabled(False)
            self.preview_button.setEnabled(False)
            self.process_button.setEnabled(False)
            
            # 获取当前帧
            frame = self.video_processor.get_frame(self.current_frame_idx)
            if frame is None:
                raise Exception("无法读取视频帧")
                
            # 检测水印区域
            region = self.video_processor.detect_watermark(frame)
            if region:
                x, y, w, h = region
                # 设置选择区域
                self.preview_label.selection = QRect(x, y, w, h)
                self.preview_label.update()
                
                # 设置水印区域
                self.video_processor.set_watermark_region(x, y, w, h)
                
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
        if not self.preview_label.selection:
            return
            
        try:
            # 获取选择区域
            rect = self.preview_label.selection
            pixmap_rect = self.preview_label.get_pixmap_rect()
            if not pixmap_rect:
                return
                
            # 计算实际坐标（考虑图片在标签中的位置和缩放）
            scale_x = self.video_processor.width / pixmap_rect.width()
            scale_y = self.video_processor.height / pixmap_rect.height()
            
            x = int((rect.x() - pixmap_rect.x()) * scale_x)
            y = int((rect.y() - pixmap_rect.y()) * scale_y)
            w = int(rect.width() * scale_x)
            h = int(rect.height() * scale_y)
            
            # 设置水印区域
            self.video_processor.set_watermark_region(x, y, w, h)
            
            # 处理当前��
            frame = self.video_processor.get_frame(self.current_frame_idx)
            if frame is not None:
                processed = self.video_processor.process_frame(frame)
                # 获取预览尺寸的帧
                preview_frame = cv2.resize(
                    processed,
                    (pixmap_rect.width(), pixmap_rect.height()),
                    interpolation=cv2.INTER_AREA
                )
                # 转换为RGB格式用于显示
                processed_rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
                self.preview_label.set_frame(processed_rgb)
                self.preview_button.setEnabled(True)
                self.process_button.setEnabled(True)
                
        except Exception as e:
            self.status_label.setText(f"预览失败: {str(e)}")
        
    def on_selection_changed(self, rect):
        """选择区域改变的处理"""
        if rect.isValid() and rect.width() > 10 and rect.height() > 10:
            self.preview_button.setEnabled(True)
            self.process_button.setEnabled(True)
            # 自动预览效果
            self.preview_removal()
        
    def switch_to_image_mode(self):
        """切换到图片模式"""
        from ui.main_window import MainWindow
        if not self.image_window:
            self.image_window = MainWindow()
        self.image_window.show()
        self.hide()
        
    def process_video(self):
        """处理视频"""
        if not self.video_processor.watermark_region or not self.video_files:
            return
            
        # 禁用所有按钮
        self.process_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.detect_button.setEnabled(False)
        self.video_list.setEnabled(False)
            
        # 创建进度对话框
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle("处理进度")
        progress_dialog.setLabelText("准备处理...")
        progress_dialog.setRange(0, 100)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.show()
        
        # 计算总进度
        total_videos = len(self.video_files)
        current_video = 0
        
        try:
            for video_path in self.video_files:
                # 检查是否取消
                if progress_dialog.wasCanceled():
                    break
                    
                # 更新进度对话框标题
                progress_dialog.setLabelText(
                    f"正在处理: {os.path.basename(video_path)}\n"
                    f"({current_video + 1}/{total_videos})"
                )
                
                # 获取输出路径
                output_path = FileHandler.get_output_path(video_path, suffix="_nowm")
                
                # 加载视频
                if not self.video_processor.load_video(video_path):
                    self.status_label.setText(f"加载失败: {os.path.basename(video_path)}")
                    current_video += 1
                    continue
                    
                # 创建处理线程
                self.process_thread = ProcessThread(self.video_processor, output_path)
                
                # 连接信号
                def update_progress(value):
                    total_progress = (current_video * 100 + value) / total_videos
                    progress_dialog.setValue(int(total_progress))
                    progress_dialog.setLabelText(
                        f"正在处理: {os.path.basename(video_path)}\n"
                        f"({current_video + 1}/{total_videos})\n"
                        f"当前进度: {value:.1f}%"
                    )
                    QApplication.processEvents()  # 确保UI更新
                    
                def on_finished(success, result):
                    nonlocal current_video
                    if success:
                        self.status_label.setText(f"处理完成: {os.path.basename(result)}")
                    else:
                        self.status_label.setText(f"处理失败: {os.path.basename(video_path)}")
                    current_video += 1
                    
                    # 清理线程
                    if self.process_thread:
                        self.process_thread.progress_updated.disconnect()
                        self.process_thread.finished.disconnect()
                        self.process_thread.deleteLater()
                        self.process_thread = None
                    
                    # 处理下一个视频或完成处理
                    if current_video == total_videos:
                        progress_dialog.setLabelText("处理完成！")
                        progress_dialog.setValue(100)
                        self.status_label.setText(f"已完成 {current_video} 个视频的处理")
                        
                        # 打开输出目录
                        try:
                            output_dir = os.path.dirname(FileHandler.get_output_path(self.video_files[0], suffix="_nowm"))
                            os.startfile(output_dir)
                        except Exception:
                            pass
                            
                        # 重新启用所有按钮
                        self.process_button.setEnabled(True)
                        self.preview_button.setEnabled(True)
                        self.detect_button.setEnabled(True)
                        self.video_list.setEnabled(True)
                    
                # 连接信号
                self.process_thread.progress_updated.connect(update_progress)
                self.process_thread.finished.connect(on_finished)
                
                # 启动处理线程
                self.process_thread.start()
                
                # 等待处理完成
                while self.process_thread and self.process_thread.isRunning():
                    QApplication.processEvents()  # 处理UI事件
                    if progress_dialog.wasCanceled():
                        if self.process_thread:
                            self.process_thread.cancel()
                            self.process_thread.wait()  # 等待线程结束
                            self.process_thread.deleteLater()
                            self.process_thread = None
                        self.status_label.setText("处理已取消")
                        break
                    QThread.msleep(50)  # 减少CPU占用
                
                # 如果取消了处理，跳出循环
                if progress_dialog.wasCanceled():
                    break
                
        except Exception as e:
            self.status_label.setText(f"处理出错: {str(e)}")
            
        finally:
            # 重新启用所有按钮
            self.process_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.detect_button.setEnabled(True)
            self.video_list.setEnabled(True)
            
            # 确保线程被清理
            if self.process_thread:
                self.process_thread.cancel()
                self.process_thread.wait()
                self.process_thread.deleteLater()
                self.process_thread = None
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止播放
        if self.playing:
            self.toggle_play()
        # 取消正在进行的处理
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.cancel()
            self.process_thread.wait()
        # 隐藏窗口而不是关闭
        self.hide()
        event.ignore()
  