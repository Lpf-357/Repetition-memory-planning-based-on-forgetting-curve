import gradio as gr
import json
import os
from datetime import datetime, timedelta
import calendar

# Data handling functions
def load_data():
    """Load data from JSON file, or initialize empty list if file doesn't exist."""
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
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
    # Format the date from components
    date_str = format_date(year, month, day)
    
    # Filter out empty items
    items = [item for item in [item1, item2, item3] if item and item.strip()]
    
    if not items:
        return "请至少添加一个学习项目", None, None
    
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

def get_reviews_due_today():
    """Get all reviews due today that haven't been completed."""
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    
    reviews_due = [
        {"entry_date": entry["date"], "items": entry["items"], "review_index": i, "due_date": review["dueDate"]}
        for entry in data 
        for i, review in enumerate(entry["reviews"])
        if review["dueDate"] == today and not review["completed"]
        and entry["date"] != today  # 排除当天添加的学习卡片
    ]
    
    # 按时间顺序排列（旧→新）
    reviews_due.sort(key=lambda x: x["entry_date"])
    
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
    data.sort(key=lambda x: x["date"], reverse=False)  # 按时间顺序排序（从旧到新）
    
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
                    choices=get_existing_dates(),
                    label="已有学习日期"
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
                    return gr.update(), gr.update(), gr.update()
                
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
                except:
                    return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
            
            # Connect the load button to load existing items
            load_existing_btn.click(
                fn=load_existing_items,
                inputs=[existing_dates_dropdown],
                outputs=[year_dropdown, month_dropdown, day_dropdown, item1, item2, item3]
            )
        
        # Tab 2: Today's Reviews
        with gr.TabItem("今日复习"):
            # 将组件定义移至标签页内部
            today_reviews_md = gr.Markdown(render_today_reviews())
            
            with gr.Row():
                # Create buttons for reviews due today
                reviews = get_reviews_due_today()
                if reviews:
                    for i in range(min(len(reviews), 10)):  # Limit to 10 buttons
                        btn = gr.Button(f"完成复习 #{i+1}")
                        # Use a closure to capture the correct index
                        btn.click(
                            fn=lambda idx=i: mark_review_completed(idx),
                            inputs=[],
                            outputs=[today_reviews_md]  # 只更新当前标签页的组件
                        ).then(
                            # 完成复习后，触发进度页刷新按钮，确保进度页也会更新
                            fn=lambda: None,
                            inputs=None,
                            outputs=None,
                            js="() => { document.querySelector('#refresh_progress_trigger button').click(); }"
                        )
                else:
                    gr.Markdown("今天没有需要复习的项目。")
        
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
                progress_md = gr.Markdown(render_progress())
                
            
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
        fn=lambda: gr.update(choices=get_existing_dates() or []),
        inputs=None,
        outputs=[existing_dates_dropdown, delete_date_dropdown]
    )
    
    # Tab change events to refresh content when tabs are selected
    def on_tab_change(tab_index):
        print(f"Received tab_index: {tab_index}")
        if tab_index == 0:  # 添加学习标签页
            return {"__type__": "update", "value": ""}  # 返回空字符串，不会影响任何组件
        elif tab_index == 1:  # 今日复习标签页
            return {"__type__": "update", "value": render_today_reviews()}
        elif tab_index == 2:  # 学习进度标签页
            return {"__type__": "update", "value": render_progress()}
        else:
            return {"__type__": "update", "value": ""}

    # 标签切换事件，仅更新当前活动标签页的内容
    tabs.change(
        fn=on_tab_change,
        outputs=[gr.Textbox(visible=False)],  # 使用隐藏的文本框作为中间值传递
        js="""
        () => {
            const tabIndex = Array.from(document.querySelectorAll('.tabs button')).findIndex(btn => btn.classList.contains('active'));
            
            // 基于当前标签页更新对应内容
            setTimeout(() => {
                const allMarkdowns = document.querySelectorAll('gradio-markdown');
                
                if (tabIndex === 1) {  // 今日复习标签页
                    // 找到今日复习标签页中的Markdown组件并更新
                    const reviewsTab = document.querySelectorAll('.tab-item')[1];
                    if (reviewsTab) {
                        const md = reviewsTab.querySelector('gradio-markdown');
                        if (md && window.updateMarkdownValue) {
                            window.updateMarkdownValue(md, result);
                        }
                    }
                } else if (tabIndex === 2) {  // 学习进度标签页
                    // 找到学习进度标签页中的Markdown组件并更新
                    const progressTab = document.querySelectorAll('.tab-item')[2];
                    if (progressTab) {
                        const md = progressTab.querySelector('gradio-markdown');
                        if (md && window.updateMarkdownValue) {
                            window.updateMarkdownValue(md, result);
                        }
                    }
                }
            }, 100);
            
            return tabIndex;
        }
        """
    ).then(
        fn=lambda: None,  # 空函数，不执行任何操作
        inputs=None,
        outputs=None,
        js="""
        (result) => {
            // 添加更新Markdown内容的辅助函数
            if (!window.updateMarkdownValue) {
                window.updateMarkdownValue = function(element, value) {
                    // 获取实际的内部DOM元素并更新内容
                    const inner = element.querySelector('.prose') || element;
                    if (inner) inner.innerHTML = value;
                };
            }
            
            const tabIndex = parseInt(result);
            if (isNaN(tabIndex)) return;
            
            // 获取所有标签页内容元素
            const tabItems = document.querySelectorAll('.tab-item');
            
            if (tabIndex === 1) {  // 今日复习标签页
                // 触发服务器端刷新
                const reviewTab = tabItems[1];
                if (reviewTab) {
                    const md = reviewTab.querySelector('gradio-markdown');
                    if (md) {
                        gradioApp().querySelector('#refresh_reviews_trigger button').click();
                    }
                }
            }
            else if (tabIndex === 2) {  // 学习进度标签页
                // 触发服务器端刷新
                const progressTab = tabItems[2];
                if (progressTab) {
                    const md = progressTab.querySelector('gradio-markdown');
                    if (md) {
                        gradioApp().querySelector('#refresh_progress_trigger button').click();
                    }
                }
            }
        }
        """
    )
    
    # 添加隐藏的刷新触发器按钮
    with gr.Row(visible=False):
        refresh_reviews_btn = gr.Button("刷新今日复习", elem_id="refresh_reviews_trigger")
        refresh_progress_btn = gr.Button("刷新学习进度", elem_id="refresh_progress_trigger")
        
        # 添加刷新按钮的事件处理
        refresh_reviews_btn.click(
            fn=lambda: render_today_reviews(),
            outputs=[today_reviews_md]
        )
        
        refresh_progress_btn.click(
            fn=lambda: render_progress(),
            outputs=[progress_md]
        )

# Launch the app
if __name__ == "__main__":
    # We'll rely on the tab change event to populate the content
    # when the user switches tabs
    app.launch()
