import gradio as gr
import json
import os
import requests
from datetime import datetime, timedelta
import calendar

# Data handling functions
def load_data():
    """Load data from JSON file, or initialize empty list if file doesn't exist."""
    try:
        # Try to open and read the file
        with open("data.json", "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                # If file exists but has invalid JSON (e.g., empty file)
                return []
    except FileNotFoundError:
        # If file doesn't exist, create it with an empty list
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return []

def save_data(data):
    """Save data to JSON file."""
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def delete_entry(date_str):
    """Delete a learning entry by date."""
    data = load_data()
    # Filter out the entry with the matching date
    data = list(filter(lambda entry: entry["date"] != date_str, data))
    save_data(data)
    return "学习记录已删除！"

def get_existing_dates():
    """Get all dates that have learning entries."""
    data = load_data()
    if not data:
        return []
    # Sort dates in descending order (newest first)
    dates = sorted((entry["date"] for entry in data), reverse=True)
    return dates

def get_items_for_date(date_str):
    """Get existing learning items for a specific date."""
    data = load_data()
    for entry in data:
        if entry["date"] == date_str:
            return entry["items"]
    return []

def calculate_review_dates(date_str):
    """Calculate review dates based on Ebbinghaus forgetting curve."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    intervals = [1, 2, 4, 7, 14, 21, 30]  # Days after initial learning
    return [{"dueDate": (date + timedelta(days=interval)).strftime("%Y-%m-%d"), 
             "completed": False} for interval in intervals]

# Date helper functions
def get_days_in_month(year, month):
    """Get the number of days in a specific month of a year."""
    return calendar.monthrange(year, month)[1]

def format_date(year, month, day):
    """Format the date components into YYYY-MM-DD."""
    try:
        year = int(year)
        month = int(month)
        day = int(day)
        # 新增日期有效性验证
        datetime(year, month, day)
    except (ValueError, TypeError) as e:
        raise gr.Error(f"无效的日期: {year}-{month}-{day}") from e
    return f"{year}-{month:02d}-{day:02d}"

# Core functionality
def add_learning_entry(year, month, day, item1, item2, item3):
    """Add a new learning entry with up to three items or update an existing one."""
    try:
        # Validate inputs first to prevent format_date errors
        if not year or not month or not day:
            return "请输入有效的日期", render_today_reviews(), render_progress()
            
        # Format the date from components
        try:
            date_str = format_date(year, month, day)
        except Exception as e:
            return f"日期格式错误: {str(e)}", render_today_reviews(), render_progress()
        
        # Filter out empty items
        items = [item for item in [item1, item2, item3] if item and item.strip()]
        
        if not items:
            return "请至少添加一个学习项目", render_today_reviews(), render_progress()
        
        # Load existing data
        data = load_data()
        
        # Check if an entry for this date already exists
        for existing_entry in data:
            if existing_entry["date"] == date_str:
                # Update the existing entry
                existing_entry["items"] = items  # Replace with new items instead of combining
                save_data(data)
                return "已更新当日学习项目！", render_today_reviews(), render_progress()
        
        # If no existing entry, create a new one
        entry = {
            "date": date_str,
            "items": items,
            "reviews": calculate_review_dates(date_str)
        }
        
        # Add new entry
        data.append(entry)
        save_data(data)
        
        # Return success message and update both today's reviews and progress
        return "学习项目已添加！", render_today_reviews(), render_progress()
    except Exception as e:
        print(f"添加学习项目出错: {str(e)}")
        return f"添加学习项目出错: {str(e)}", render_today_reviews(), render_progress()

def get_reviews_due_today():
    """Get all reviews due today that haven't been completed."""
    data = load_data()
    if not data:
        return []
        
    today = datetime.now().strftime("%Y-%m-%d")
    
    reviews_due = [
        {"entry_date": entry["date"], "items": entry["items"], "review_index": i, "due_date": review["dueDate"]}
        for entry in data 
        for i, review in enumerate(entry["reviews"])
        if review["dueDate"] == today and not review["completed"]
        # 移除"排除当天添加的学习卡片"条件，允许显示所有需要复习的卡片
    ]
    
    # 按时间逆序排列（新→旧）
    reviews_due.sort(key=lambda x: x["entry_date"], reverse=True)
    
    return reviews_due

def mark_review_completed(entry_index):
    data = load_data()
    reviews = get_reviews_due_today()
    
    if 0 <= entry_index < len(reviews):
        review = reviews[entry_index]
        
        # 使用next()查找匹配的条目
        entry = next((e for e in data if e["date"] == review["entry_date"]), None)
        if entry:
            entry["reviews"][review["review_index"]]["completed"] = True
            save_data(data)
    
    # 只返回今日复习内容，不再返回两个值
    return render_today_reviews()

# UI rendering functions
# 在UI rendering functions区域新增
def generate_items_html(items, with_delete=False):
    """生成统一的学习项目HTML，可选是否包含删除按钮"""
    items_html = '<div class="learning-items"><span class="section-title">学习内容:</span>'
    for item in items:
        items_html += '<div class="learning-item-container">'
        items_html += f'<div class="learning-item">{item}</div>'
        if with_delete:
            items_html += '<div class="delete-item-btn" title="删除此项目" onclick="alert(\'单项删除功能将在下一版本推出！\')">×</div>'
        items_html += '</div>'
    items_html += '</div>'
    return items_html

# 修改render_today_reviews中的对应部分
def render_today_reviews():
    """Render the reviews due today using progress card style."""
    reviews = get_reviews_due_today()
    
    if not reviews:
        return "今天没有需要复习的项目。"
    
    markdown = "## 今日复习\n\n"
    
    for review in reviews:
        items_html = generate_items_html(review["items"])  # 替换原有生成逻辑
        markdown += f"""
<div class="learning-card">
    <div class="status-bar">
        <div class="status-date"><span class="section-title">学习日期:</span> {review['entry_date']}</div>
        <div class="progress-indicator" style="background-color: #e3f2fd; color: #0d47a1; border: 1px solid #90caf9">
            复习阶段: {review['review_index'] + 1}/7
        </div>
    </div>
    {items_html}
</div>
"""
    
    return markdown

# 修改render_progress中的对应部分
def render_progress():
    """Render the progress of all entries as Markdown."""
    data = load_data()
    
    if not data:
        return "尚未添加任何学习项目。"
    
    # Sort data by date, oldest first (chronological order)
    data.sort(key=lambda x: x["date"], reverse=True)  # 按时间逆序排序（从新到旧）
    
    markdown = "## 学习进度\n\n"
    
    # Add some CSS styling for better layout
    markdown += """
<style>
/* Base card styles */
.learning-card {
    margin-bottom: 24px;
    padding: 20px;
    border-radius: 12px;
    background: linear-gradient(145deg, #ffffff, #f8f9fa);
    border: 2px solid #2e86de;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    position: relative;
    transform: translateY(0);
    opacity: 1;
    will-change: transform, opacity;
    transition: all 0.3s ease;
    cursor: default;
}

/* 优化后的进度指示器文字样式 */
.progress-indicator {
    font-weight: 700;
    font-size: 0.92em;
    letter-spacing: 0.3px;
    text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    padding: 4px 8px;
    border-radius: 4px;
}

.learning-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.15);
}

/* Status bar styles */
.status-bar {
    display: flex;
    align-items: center;
    font-size: 0.9em;
    color: #222222;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 10px;
    margin-bottom: 14px;
}

.status-date {
    flex: 1;  /* 占据左侧空间 */
}

.progress-indicator {
    margin: 0 auto;
    display: inline-block;
    padding: 8px 16px;
    border-radius: 16px;
    background-color: #2e86de;
    color: white;
    font-weight: 700;
    text-align: center;
    min-width: 140px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
}

.progress-indicator:hover {
    transform: scale(1.02);
    box-shadow: 0 3px 6px rgba(0,0,0,0.15);
}

/* Delete button for individual learning items */
.learning-item-container {
    position: relative;
}

.delete-item-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 22px;
    height: 22px;
    background-color: #ffebee;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: #b71c1c;
    font-weight: bold;
    font-size: 0.8em;
    border: 1px solid #ef9a9a;
    opacity: 0;
    transition: all 0.2s ease;
}

.learning-item-container:hover .delete-item-btn {
    opacity: 0.8;
}

.delete-item-btn:hover {
    opacity: 1;
    background-color: #ef5350;
    color: white;
}

/* Learning items container */
.learning-items {
    margin-bottom: 14px;
    color: #222222;
}

/* Individual learning item */
.learning-item {
    display: block;
    font-size: 1.1em;
    padding: 10px 14px;
    margin-bottom: 8px;
    background-color: #edf2fa;
    border-radius: 6px;
    border-left: 3px solid #2e86de;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    font-weight: 600;
    color: #1a1a1a;
    letter-spacing: 0.01em;
    padding-right: 40px; /* Space for delete button */
}

/* Review dates container */
.review-dates {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
}

/* Base review date style */
.review-date {
    font-size: 0.9em;
    padding: 5px 10px;
    border-radius: 4px;
    border: 1px solid #e0e0e0;
    background-color: #f5f5f5;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    font-weight: 600;
}

/* Completed review */
.review-completed {
    background-color: #e8f5e9;
    border-color: #a5d6a7;
    color: #1b5e20;
    font-weight: 600;
}

/* Pending review */
.review-pending {
    background-color: #e3f2fd;
    border-color: #90caf9;
    color: #0d47a1;
    font-weight: 600;
}

/* Overdue review */
.review-overdue {
    background-color: #ffebee;
    border-color: #ef9a9a;
    color: #b71c1c;
    font-weight: 600;
}

/* Section titles */
.section-title {
    font-weight: 700;
    color: #1a1a1a;
    margin-right: 8px;
    display: block;
    margin-bottom: 10px;
}

/* Global text styles - apply to entire app */
body, div, p, span {
    color: #1a1a1a !important;
    font-weight: normal !important;
}

/* Bold text on colored backgrounds - MODIFIED to exclude progress indicator */
div[style*="background-color"]:not(.progress-indicator) {
    font-weight: 600 !important;
    color: white !important;
    text-shadow: 0px 1px 1px rgba(0, 0, 0, 0.2) !important;
}

/* Make progress indicator text color take precedence */
.progress-indicator {
    font-weight: 700 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
    color: inherit !important;
}

/* Confirmation dialog styles */
.confirm-dialog {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.dialog-content {
    background-color: white;
    padding: 24px;
    border-radius: 8px;
    width: 400px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}

.dialog-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 20px;
}

.dialog-buttons button {
    padding: 8px 16px;
    border-radius: 4px;
    border: none;
    font-weight: 600;
    cursor: pointer;
}

.btn-cancel {
    background-color: #e0e0e0;
    color: #424242;
}

.btn-confirm {
    background-color: #f44336;
    color: white;
}
</style>
"""
    
    # Generate cards for each learning entry
    for entry in data:
        completed_count = sum(1 for review in entry["reviews"] if review["completed"])
        progress_color = "#e8f5e9" if completed_count == 7 else "#fff3e0" if completed_count > 3 else "#ffebee"
        progress_text_color = "#004d40" if completed_count == 7 else "#bf360c" if completed_count > 3 else "#b71c1c"
        progress_border = "#a5d6a7" if completed_count == 7 else "#ffcc80" if completed_count > 3 else "#ef9a9a"
        
        # Generate items section with delete buttons
        items_html = generate_items_html(entry["items"], with_delete=True)
        
        # Generate review dates section
        today = datetime.now().strftime("%Y-%m-%d")
        review_dates_html = '<div class="review-dates">'
        
        for i, review in enumerate(entry["reviews"]):
            review_date = review["dueDate"]
            is_completed = review["completed"]
            is_overdue = not is_completed and review_date < today
            
            # Determine the appropriate CSS class based on status
            css_class = "review-completed" if is_completed else "review-overdue" if is_overdue else "review-pending"
            status_text = "已完成" if is_completed else "逾期" if is_overdue else "待复习"
            
            review_dates_html += f'<div class="review-date {css_class}">第{i+1}次: {review_date} ({status_text})</div>'
        
        review_dates_html += '</div>'
        
        # Create the card with all information and delete button
        markdown += f"""
<div class="learning-card">
    <div class="status-bar">
        <div class="status-date"><span class="section-title">学习日期:</span> {entry['date']}</div>
        <div class="progress-indicator" style="background-color: {progress_color}; color: {progress_text_color}; border: 1px solid {progress_border}">
            复习完成: {completed_count}/7
        </div>
        <div style="flex: 1;"></div> <!-- 右侧空白占位 -->
    </div>
    {items_html}
    <div class="review-schedule">
        <span class="section-title">复习计划:</span>
        {review_dates_html}
    </div>
</div>
"""
    
    # Update JavaScript to use Gradio's event handling
    markdown += """
<script>
// Function to delete an entry with animation
function deleteEntry(date) {
    if (confirm("确定要删除这个学习记录吗？此操作不可撤销。")) {
        const card = document.getElementById(`card-${date}`);
        if (card) {
            // 启动删除动画
            card.style.willChange = 'transform, opacity';
            card.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
            card.style.opacity = '0';
            card.style.transform = 'translateX(-100%) rotate(-5deg)';
            
            // 在动画结束后执行删除操作
            card.addEventListener('transitionend', () => {
                // 使用Gradio的API触发删除操作
                const deleteEvent = new CustomEvent('delete-entry', {
                    detail: { date: date }
                });
                document.dispatchEvent(deleteEvent);
            }, { once: true });
        }
    }
}

// 监听自定义删除事件
document.addEventListener('delete-entry', (e) => {
    const date = e.detail.date;
    // 通过Gradio组件ID获取输入框和按钮
    const deleteInput = gradioApp().querySelector('#delete_date_input textarea');
    const deleteButton = gradioApp().querySelector('#delete_trigger button');
    
    if (deleteInput && deleteButton) {
        deleteInput.value = date;
        deleteInput.dispatchEvent(new Event('input', { bubbles: true }));
        
        // 添加微延迟确保值更新
        setTimeout(() => {
            deleteButton.click();
        }, 50);
    }
});

// 卡片入场动画
document.addEventListener('DOMContentLoaded', function() {
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1 && node.classList.contains('learning-card')) {
                    // 仅保留基础动画效果
                    node.style.transform = 'translateY(0)';
                    node.style.opacity = '1';
                }
            });
        });
    });

    observer.observe(gradioApp(), {
        childList: true,
        subtree: true
    });
});
</script>
<div id="progress-container"></div>
"""
    
    return markdown

# Function to handle deletion from UI and refresh progress
# 修改删除处理函数
def handle_delete(date_str):
        """删除指定日期的学习记录，并更新界面"""
        current_dates = get_existing_dates() or []  # 确保始终返回列表
        if not date_str:
            return (
                "请选择一个日期！",
                gr.update(choices=current_dates),  # 保持当前选项
                gr.update(choices=current_dates),
                render_progress(),
                render_today_reviews()
            )
        
        result = delete_entry(date_str)
        updated_dates = get_existing_dates() or []
        return (
            f"已删除 {date_str} 的学习记录！",
            gr.update(choices=updated_dates),
            gr.update(choices=updated_dates),
            render_progress(),
            render_today_reviews()
        )


# Gradio interface
with gr.Blocks(title="间隔重复记忆应用") as app:
    gr.Markdown("""
    # 间隔重复记忆应用

    基于艾宾浩斯遗忘曲线，帮助你安排学习内容的复习计划。

    <style>
    .hidden {
        display: none;
    }
    /* 添加加载状态指示器 */
    .loading-indicator {
        text-align: center;
        padding: 20px;
        color: #666;
    }
    .loading-spinner {
        display: inline-block;
        width: 50px;
        height: 50px;
        border: 3px solid rgba(0, 0, 0, 0.1);
        border-radius: 50%;
        border-top-color: #2e86de;
        animation: spin 1s ease-in-out infinite;
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    </style>
    """)
    
    # 完全移除结果文本框组件
    
    # Function to handle deletion from UI and refresh progress
    
    with gr.Tabs() as tabs:
        # Tab 1: Add Learning Entry
        with gr.TabItem("添加学习"):
            with gr.Row():
                gr.Markdown("### 选择学习日期")
            
            with gr.Row():
                # Get current date for default values
                current_date = datetime.now()
                current_year = current_date.year
                current_month = current_date.month
                current_day = current_date.day
                
                # Year dropdown (range of 5 years around current year)
                year_dropdown = gr.Dropdown(
                    choices=[str(y) for y in range(current_year-2, current_year+3)],
                    value=str(current_year),
                    label="年"
                )
                
                # Month dropdown
                month_dropdown = gr.Dropdown(
                    choices=[str(m) for m in range(1, 13)],
                    value=str(current_month),
                    label="月"
                )
                
                # Day dropdown (will be updated based on month/year selection)
                day_dropdown = gr.Dropdown(
                    choices=[str(d) for d in range(1, get_days_in_month(current_year, current_month) + 1)],
                    value=str(current_day),
                    label="日"
                )
            
            with gr.Row():
                gr.Markdown("### 或选择已有学习日期")
            
            with gr.Row():
                # Dropdown to select existing dates
                existing_dates_dropdown = gr.Dropdown(
                    choices=get_existing_dates() or [],
                    label="已有学习日期",
                    value=None
                )
                load_existing_btn = gr.Button("加载已有学习项目")
            
            with gr.Row():
                item1 = gr.Textbox(label="学习项目 1", placeholder="例如：英语单词")
                item2 = gr.Textbox(label="学习项目 2 (可选)", placeholder="例如：数学公式")
                item3 = gr.Textbox(label="学习项目 3 (可选)", placeholder="例如：物理定律")
            
            add_btn = gr.Button("添加/更新学习项目")
            result_msg = gr.Markdown(elem_classes=["temporary-msg"])
            
            # Update days in month when year or month changes
            def update_days(year, month):
                year = int(year)
                month = int(month)
                days = get_days_in_month(year, month)
                return gr.update(choices=[str(d) for d in range(1, days + 1)])
            
            year_dropdown.change(
                fn=update_days, 
                inputs=[year_dropdown, month_dropdown], 
                outputs=[day_dropdown]
            )
            
            month_dropdown.change(
                fn=update_days, 
                inputs=[year_dropdown, month_dropdown], 
                outputs=[day_dropdown]
            )
            
            # Function to load existing items for a selected date
            def load_existing_items(date_str):
                if not date_str:
                    return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
                
                # Parse the date to update the date dropdowns
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    year_value = str(date_obj.year)
                    month_value = str(date_obj.month)
                    day_value = str(date_obj.day)
                    
                    # Get the items for this date
                    items = get_items_for_date(date_str)
                    
                    # Fill the text boxes with existing items
                    item1_value = items[0] if len(items) > 0 else ""
                    item2_value = items[1] if len(items) > 1 else ""
                    item3_value = items[2] if len(items) > 2 else ""
                    
                    return gr.update(value=year_value), gr.update(value=month_value), gr.update(value=day_value), gr.update(value=item1_value), gr.update(value=item2_value), gr.update(value=item3_value)
                except Exception as e:
                    # Log the error and provide default values
                    print(f"Error loading existing items: {str(e)}")
                    return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
            
            # Connect the load button to load existing items
            load_existing_btn.click(
                fn=load_existing_items,
                inputs=[existing_dates_dropdown],
                outputs=[year_dropdown, month_dropdown, day_dropdown, item1, item2, item3]
            )
        
        # Tab 2: Today's Reviews
        with gr.TabItem("今日复习"):
            # First display the reviews
            today_reviews_md = gr.Markdown(
                render_today_reviews(),
                elem_id="today_reviews_area"
            )
            feedback_msg = gr.Markdown("")  # For user feedback
            
            # Create a single dynamic button
            mark_complete_btn = gr.Button("完成复习", variant="primary")
            
            # Update button text and state based on reviews
            def update_review_ui():
                try:
                    reviews = get_reviews_due_today()
                    if reviews:
                        return gr.update(value=f"完成复习（剩余 {len(reviews)} 项）", interactive=True), render_today_reviews(), ""
                    else:
                        return gr.update(value="今日无复习项目", interactive=False), "今天没有需要复习的项目。", ""
                except Exception as e:
                    print(f"更新复习UI出错: {str(e)}")
                    return gr.update(value="今日复习（加载错误）", interactive=False), "加载复习内容时出错，请刷新页面重试。", str(e)
            
            # Enhanced mark_review_completed function
            def mark_review_completed_enhanced():
                data = load_data()
                reviews = get_reviews_due_today()
                
                if not reviews:
                    return "今天没有需要复习的项目。", "没有待复习项目"
                
                try:
                    review = reviews[0]  # Always take the first review
                    entry = next((e for e in data if e["date"] == review["entry_date"]), None)
                    
                    if entry:
                        entry["reviews"][review["review_index"]]["completed"] = True
                        save_data(data)
                        return render_today_reviews(), "复习已完成！"
                except Exception as e:
                    return render_today_reviews(), f"处理复习时出错: {str(e)}"
                
                return render_today_reviews(), "处理复习时出错，请重试。"
            
            # Button click event chain
            # 添加HTML标记以支持update_review_ui事件触发
            custom_js = """
            <script>
            // 为update_review_ui事件添加监听器
            document.addEventListener('update_review_ui', () => {
                // 模拟点击update_review_ui按钮
                const reviewUpdateButton = document.querySelector('#review_update_button button');
                if (reviewUpdateButton) {
                    reviewUpdateButton.click();
                }
            });
            </script>
            """
            gr.HTML(custom_js, visible=False)
            
            # 隐藏的更新触发器
            with gr.Row(visible=False):
                review_update_btn = gr.Button("更新复习UI", elem_id="review_update_button")
                review_update_btn.click(
                    fn=update_review_ui,
                    outputs=[mark_complete_btn, today_reviews_md, feedback_msg]
                )
            
            # 主按钮事件
            mark_complete_btn.click(
                fn=mark_review_completed_enhanced,
                outputs=[today_reviews_md, feedback_msg]
            ).then(
                fn=update_review_ui,
                outputs=[mark_complete_btn, today_reviews_md, feedback_msg]
            ).then(
                fn=lambda: None,
                js="""
                () => { 
                    // Refresh progress tab
                    document.querySelector('#refresh_progress_trigger button').click();
                }
                """
            )
            
            # 使用正确的方式初始化UI：通过tabs的选择事件
            # 不再使用错误的tabs.select直接调用方法
        
        # Tab 3: Progress
        with gr.TabItem("学习进度") as progress_tab:
            with gr.Column():
                # 删除功能置顶
                with gr.Row():
                    delete_date_dropdown = gr.Dropdown(
                        label="选择要删除的学习日期",
                        choices=get_existing_dates(),
                        interactive=True,
                        elem_id="delete_date_dropdown"
                    )
                    delete_btn = gr.Button("删除记录", variant="stop")
                
                # 进度展示在下（自动置顶后无需额外样式）
                progress_md = gr.Markdown(
                render_progress(),
                elem_id="progress_area"
            )
                
            
            # Connect the delete button to the deletion function - scoped to this tab
            # 添加删除结果提示组件
            delete_result_msg = gr.Markdown()
            
            # 更新删除按钮的事件绑定（修复输出参数数量）
            delete_btn.click(
                fn=handle_delete,
                inputs=[delete_date_dropdown],
                outputs=[
                    delete_result_msg,  # 删除结果提示
                    delete_date_dropdown,  # 删除日期下拉菜单
                    existing_dates_dropdown,  # 新增：添加页面的下拉菜单
                    progress_md,  # 进度显示
                    today_reviews_md  # 今日复习显示
                ]
            ).then(
                # 将两个单独的then调用合并为一个，同时更新两个组件
                fn=lambda: (gr.update(value=""), gr.update(choices=get_existing_dates())),
                inputs=None,
                outputs=[delete_result_msg, existing_dates_dropdown],
                js="() => new Promise(resolve => setTimeout(() => resolve(), 3000))"
            )
            
        # Tab 4: AI Analysis
        with gr.TabItem("AI分析"):
            gr.Markdown("### AI 分析\n选择一个日期范围，将学习数据发送给 AI 进行分析")
            
            with gr.Row():
                gr.Markdown("#### 开始日期")
            with gr.Row():
                start_year = gr.Dropdown(label="年", choices=[str(y) for y in range(2023, 2027)], value=None)
                start_month = gr.Dropdown(label="月", choices=[str(m) for m in range(1, 13)], value=None)
                start_day = gr.Dropdown(label="日", choices=[str(d) for d in range(1, 32)], value=None)
            
            with gr.Row():
                gr.Markdown("#### 结束日期")
            with gr.Row():
                end_year = gr.Dropdown(label="年", choices=[str(y) for y in range(2023, 2027)], value=None)
                end_month = gr.Dropdown(label="月", choices=[str(m) for m in range(1, 13)], value=None)
                end_day = gr.Dropdown(label="日", choices=[str(d) for d in range(1, 32)], value=None)
            
            send_to_ai_btn = gr.Button("AI分析")
            ai_result_md = gr.Markdown()
            
            # Update day choices for start date
            def update_start_days(year, month):
                return update_days(year, month)
            
            start_year.change(fn=update_start_days, inputs=[start_year, start_month], outputs=[start_day])
            start_month.change(fn=update_start_days, inputs=[start_year, start_month], outputs=[start_day])
            
            # Update day choices for end date
            def update_end_days(year, month):
                return update_days(year, month)
            
            end_year.change(fn=update_end_days, inputs=[end_year, end_month], outputs=[end_day])
            end_month.change(fn=update_end_days, inputs=[end_year, end_month], outputs=[end_day])
            
            # Define send_to_ai function
            def send_to_ai(start_year, start_month, start_day, end_year, end_month, end_day):
                try:
                    # Format dates
                    start_date = format_date(int(start_year), int(start_month), int(start_day))
                    end_date = format_date(int(end_year), int(end_month), int(end_day))
                    
                    if start_date > end_date:
                        return "开始日期必须早于或等于结束日期。"
                    
                    data = load_data()
                    filtered_data = [entry for entry in data if start_date <= entry["date"] <= end_date]
                    
                    if not filtered_data:
                        return "在所选时间段内没有找到数据。"
                    
                    # Include all required fields: date, items, and reviews
                    extracted_data = [
                        {
                            "date": entry["date"],        # Learning date in yyyy-MM-dd format
                            "items": entry["items"],      # Learning items (up to 3 strings)
                            "reviews": entry["reviews"]   # Review data (7 objects with dueDate and completed fields)
                        } for entry in filtered_data
                    ]
                    
                    # Create payload with data and instructions
                    payload = {
                        "data": extracted_data,
                        "instructions": """请分析用户提供的学习数据，数据包含以下字段：date：学习日期，格式为"yyyy-MM-dd"。items：学习项目，最多三个，每个项目为字符串。reviews：复习情况，包含七个对象，每个对象有dueDate（复习日期）和completed（是否完成）两个字段。
基于这些数据，请完成以下任务：分析用户最近的学习情况，包括学习频率、学习内容的种类和分布。统计复习任务的完成情况，指出哪些复习阶段的完成率较高或较低。提供学习和复习的改进建议，帮助用户优化学习计划和方法。以清晰、简洁的方式呈现分析结果，便于用户理解和应用。"""
                    }
                    
                    # API endpoint (should be replaced with actual endpoint)
                    API_URL = "https://your-api-endpoint.com/analyze"
                    
                    # Send request to AI API
                    response = requests.post(API_URL, json=payload)
                    
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            
                            # Parse the AI analysis results
                            frequency = result.get("learning_frequency", "No data available")
                            distribution = result.get("content_distribution", "No data available")
                            completion = result.get("review_completion", "No data available")
                            suggestions = result.get("suggestions", [])
                            
                            # Format as Markdown
                            markdown = (
                                f"**学习频率分析:**\n{frequency}\n\n"
                                f"**学习内容分布:**\n{distribution}\n\n"
                                f"**复习完成情况:**\n{completion}\n\n"
                                f"**改进建议:**\n"
                            )
                            
                            for sugg in suggestions:
                                markdown += f"- {sugg}\n"
                                
                            return markdown
                        except json.JSONDecodeError:
                            return "API 响应不是有效的 JSON 格式。"
                    else:
                        return f"API 请求失败，状态码: {response.status_code}"
                except Exception as e:
                    return f"错误: {str(e)}"
            
            # Connect the button to the function
            send_to_ai_btn.click(
                fn=send_to_ai,
                inputs=[start_year, start_month, start_day, end_year, end_month, end_day],
                outputs=[ai_result_md]
            )
    
# Add learning entry event
    add_btn.click(
        fn=add_learning_entry,
        inputs=[year_dropdown, month_dropdown, day_dropdown, item1, item2, item3],
        outputs=[result_msg, today_reviews_md, progress_md]  # 更新所有相关组件
    ).then(
        fn=lambda: gr.update(value=""),
        inputs=None,
        outputs=result_msg,
        js="() => new Promise(resolve => setTimeout(() => resolve(), 3000))"
    ).then(
        # 修改这里：确保获取最新的日期列表并同时更新两个下拉菜单
        fn=lambda: (
            gr.update(choices=get_existing_dates() or []), 
            gr.update(choices=get_existing_dates() or [])
        ),
        inputs=None,
        outputs=[existing_dates_dropdown, delete_date_dropdown]
    )
    
    # 处理标签页切换事件
    def on_tab_select(tab_index):
        """处理标签页切换事件"""
        try:
            existing_dates = get_existing_dates() or []  # 确保始终是列表
            
            if tab_index == 0:  # "添加学习"页
                return (
                    gr.update(choices=existing_dates),  # 更新existing_dates_dropdown
                    gr.update(),  # today_reviews_md无需更新
                    gr.update(choices=existing_dates),  # 更新delete_date_dropdown
                    render_progress()  # 更新progress_md
                )
            elif tab_index == 1:  # "今日复习"页
                return (
                    gr.update(), 
                    render_today_reviews(),  # 立即更新今日复习内容
                    gr.update(), 
                    gr.update()
                )
            elif tab_index == 2:  # "学习进度"页
                return (
                    gr.update(),
                    gr.update(),
                    gr.update(choices=existing_dates),
                    render_progress()
                )
            elif tab_index == 3:  # "AI Analysis"页
                return (
                    gr.update(),
                    gr.update(),
                    gr.update(choices=existing_dates),
                    gr.update()
                )
            else:
                return (gr.update(), gr.update(), gr.update(), gr.update())
        except Exception as e:
            print(f"标签页切换错误: {str(e)}")
            # 出现错误时提供安全的默认值
            return (
                gr.update(choices=[]), 
                "加载内容时出错，请刷新页面重试。", 
                gr.update(choices=[]), 
                "加载内容时出错，请刷新页面重试。"
            )

    # 绑定新的标签页选择事件
    # 使用tab_index作为参数而不是tabs对象
    tabs.select(
        fn=lambda tab_index: on_tab_select(tab_index),
        outputs=[
            existing_dates_dropdown, 
            today_reviews_md, 
            delete_date_dropdown, 
            progress_md
        ]
    ).then(
        # 仅当切换到"今日复习"页时更新按钮状态
        fn=lambda tab_index: update_review_ui() if tab_index == 1 else (gr.update(), gr.update(), gr.update()),
        outputs=[mark_complete_btn, today_reviews_md, feedback_msg]
    )
    
    # 添加隐藏的刷新触发器按钮
    with gr.Row(visible=False):
        refresh_reviews_btn = gr.Button("刷新今日复习", elem_id="refresh_reviews_trigger")
        refresh_progress_btn = gr.Button("刷新学习进度", elem_id="refresh_progress_trigger")
        refresh_dropdowns_btn = gr.Button("刷新下拉菜单", elem_id="refresh_dropdowns_trigger")
        
        # 添加刷新按钮的事件处理
        refresh_reviews_btn.click(
            fn=lambda: render_today_reviews(),
            outputs=[today_reviews_md]
        )
        
        refresh_progress_btn.click(
            fn=lambda: render_progress(),
            outputs=[progress_md]
        )
        
        # 添加刷新下拉菜单的事件处理
        refresh_dropdowns_btn.click(
            fn=lambda: (
                gr.update(choices=get_existing_dates() or []),
                gr.update(choices=get_existing_dates() or [])
            ),
            outputs=[existing_dates_dropdown, delete_date_dropdown]
        )

# Launch the app
if __name__ == "__main__":
    # Run initialization to ensure data.json exists
    load_data()
    
    # We'll rely on the tab change event to populate the content
    # when the user switches tabs
    app.launch()
