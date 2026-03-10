# -*- coding: utf-8 -*-
"""
OBS Display
Each output file (title, summary, suggestion) supports individual HTML generation.
"""

import os
import re
import html as html_module
import webbrowser
from tkinter import messagebox
from typing import Tuple, Optional


class OBSDisplayHelper:
    """
    OBS Display

    titlesummarysuggestion:
    - HTML
    - CSS/JavaScript
    -

    """

    def __init__(self, project_root: str, config: dict, save_config_callback):
        """


        Args:
            project_root:
            config:
            save_config_callback:
        """
        self.project_root = project_root
        self.config = config
        self.save_config_callback = save_config_callback
        self.output_types = ['title', 'summary', 'facilitator']
        self.labels = {
            'title': '',
            'summary': '',
            'facilitator': ''
        }
        self.icons = {
            'title': '',
            'summary': '',
            'facilitator': ''
        }

    def get_html_path(self, output_type):
        """HTML"""
        return os.path.join(
    self.project_root,
    'output',
     f'obs_{output_type}.html')

    def get_source_file_path(self, output_type):
        """"""
        return os.path.join(self.project_root, 'output', f'{output_type}.txt')

    def read_file_safe(self, file_path):
        """"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return ""
        except Exception as e:
            return f"Error reading file: {e}"

    def get_default_css(self, output_type):
        """CSS"""
        label = self.labels[output_type]
        icon = self.icons[output_type]

        return f"""/* OBS Display - {label} */

/*  */
body {{
    margin: 0;
    padding: 20px;
    font-family: 'Arial', 'Meiryo', sans-serif;
    background: transparent;  /* OBS */
    color: #ffffff;
}}

/*  */
.content {{
    background: rgba(0, 0, 0, 0.75);  /*  */
    border-left: 5px solid #00d4ff;  /*  */
    padding: 25px 30px;
    border-radius: 12px;
    box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
    max-width: 900px;
}}

/*  */
.label {{
    color: #00d4ff;  /*  */
    font-size: 22px;
    font-weight: bold;
    margin-bottom: 18px;
    text-transform: uppercase;
    letter-spacing: 2px;
    text-shadow: 0 0 12px rgba(0, 212, 255, 0.9);
}}

/*  */
.text {{
    font-size: 20px;
    line-height: 1.9;
    white-space: pre-wrap;  /*  */
    word-wrap: break-word;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}}

/*  */
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(15px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

.content {{
    animation: fadeIn 0.6s ease-out;
}}

/*  */
@keyframes glow {{
    0%, 100% {{ box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4); }}
    50% {{ box-shadow: 0 5px 30px rgba(0, 212, 255, 0.7); }}
}}

    animation: fadeIn 0.6s ease-out, glow 3s ease-in-out infinite;
}}"""

    def get_character_css(self, output_type):
        """CSS"""
        label = self.labels[output_type]
        # icon = self.icons[output_type] #

        return f"""/* OBS Display - {label} (Character Mode) */

/*  */
body {{
    margin: 0;
    padding: 20px;
    font-family: 'Arial', 'Meiryo', sans-serif;
    background: transparent;
    color: #333;
    overflow: hidden; /*  */
}}

/* Character CSS */
.character-img {{
    position: fixed;
    bottom: -10px;
    right: 20px;
    width: 250px; /* Image size */
    height: auto;
    z-index: 10;
    filter: drop-shadow(2px 2px 5px rgba(0,0,0,0.3));
    animation: slideUp 0.8s ease-out;
}}

/* Bubble Container */
.bubble-container {{
    position: fixed;
    bottom: 180px; /* Near character head */
    right: 40px;
    width: 600px;
    display: flex;
    justify-content: flex-end;
    z-index: 5;
}}

/* Bubble Content */
.content {{
    position: relative;
    background: #ffffff;
    border: 4px solid #333;
    border-radius: 20px;
    padding: 20px 30px;
    box-shadow: 5px 5px 0px rgba(0,0,0,0.2);
    max-width: 100%;
}}

/* Bubble Tail */
.content::after {{
    content: '';
    position: absolute;
    bottom: -15px;
    right: 60px;
    width: 0;
    height: 0;
    border-left: 15px solid transparent;
    border-right: 15px solid transparent;
    border-top: 15px solid #333;
}}

.content::before {{
    content: '';
    position: absolute;
    bottom: -9px;
    right: 63px;
    width: 0;
    height: 0;
    border-left: 12px solid transparent;
    border-right: 12px solid transparent;
    border-top: 12px solid #ffffff;
    z-index: 1;
}}

/* Label */
.label {{
    color: #555;
    font-size: 14px;
    font-weight: bold;
    margin-bottom: 5px;
    text-align: right;
}}

/* Text Content */
.text {{
    font-size: 22px;
    line-height: 1.6;
    font-weight: bold;
    color: #1a1a1a;
    white-space: pre-wrap;
    word-wrap: break-word;
}}

/* Animation */
@keyframes slideUp {{
    from {{ transform: translateY(100%); opacity: 0; }}
    to {{ transform: translateY(0); opacity: 1; }}
}}

@keyframes popIn {{
    from {{ transform: scale(0.8); opacity: 0; }}
    to {{ transform: scale(1); opacity: 1; }}
}}

.content {{
    animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    transform-origin: bottom right;
}}"""

    def get_default_js(self, output_type='summary'):
        """Get default JavaScript."""
        data_file = f'./obs_{output_type}_data.js'

        return f"""// JavaScript for OBS Display
// JSONP polling method

//
const DATA_SCRIPT_PATH = '{data_file}';
const POLL_MS = 1000;
const AUTO_CYCLE_MS = 60000;

const el = document.querySelector('.text');
let lastText = '';
let lastUpdateAt = Date.now();

//
function setTextWithAnimation(txt) {{
    el.textContent = txt || '';
    el.classList.remove('slide-in');
    void el.offsetWidth;
    el.classList.add('slide-in');
}}

// :
window.updateContent = function (txt) {{
    const normalized = (txt || '').trim();
    if (normalized !== lastText) {{
        lastText = normalized;
        setTextWithAnimation(normalized);
        lastUpdateAt = Date.now();
    }}
}};

// JSONP
function pollData() {{
    const oldScript = document.getElementById('data-script');
    if (oldScript) {{
        oldScript.remove();
    }}

    const script = document.createElement('script');
    script.id = 'data-script';
    script.src = DATA_SCRIPT_PATH + '?t=' + Date.now();
    document.body.appendChild(script);
}}

//
setInterval(pollData, POLL_MS);
pollData(); //

//
setInterval(() => {{
    const inactive = Date.now() - lastUpdateAt >= AUTO_CYCLE_MS;
    if (inactive && lastText) {{
        setTextWithAnimation(lastText);
        lastUpdateAt = Date.now();
    }}
}}, 1000);

//
document.addEventListener('DOMContentLoaded', function() {{
    console.log('OBS Display loaded - polling ' + DATA_SCRIPT_PATH);
}});"""


    def _format_text_to_html(self, text: str) -> str:
        """
        Convert basic markdown and newlines to HTML for OBS display.
        Removes strict html.escape() to allow formatting, but escapes basic entities
        first, then applies formatting.
        """
        if not text:
            return ""
        
        # First, escape basic HTML to prevent raw script injection but allow our own tags
        text = html_module.escape(text)

        # Basic markdown to HTML conversion
        # Bold: **text**
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Italic: *text* (excluding already matched bold if we used a better regex, but this simple one works for most cases)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        # Strikethrough: ~~text~~
        text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)
        
        # Convert newlines to <br> for HTML rendering
        text = text.replace('\n', '<br>')
        
        return text

    def generate_html(
    self,
    output_type,
    custom_css,
    custom_js,
     style_mode='standard'):
        """HTML"""
        try:
            #
            source_path = self.get_source_file_path(output_type)
            text_content = self.read_file_safe(source_path)

            # HTML
            text_escaped = self._format_text_to_html(text_content)

            #
            label = self.labels[output_type]
            icon = self.icons[output_type]

            # HTML
            body_content = ""
            if style_mode == 'character':
                #  (HTML)
                # output/obs_xxx.html -> assets/bloson.png
                img_path = "../assets/bloson.png"
                body_content = f"""
    <img src="{img_path}" class="character-img" alt="Character">
    <div class="bubble-container">
        <div class="content">
            <div class="label">{label}</div>
            <div class="text">{text_escaped}</div>
        </div>
    </div>"""
            else:
                #
                body_content = f"""
    <div class="content">
        <div class="label">{icon} {label}</div>
        <div class="text">{text_escaped}</div>
    </div>"""

            # HTML
            html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OBS Display - {label}</title>
    <style>
{custom_css}
    </style>
</head>
<body>
{body_content}

    <script>
{custom_js}
    </script>
</body>
</html>"""


            # HTML
            html_path = self.get_html_path(output_type)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            return True, html_path

        except Exception as e:
            return False, str(e)

    def preview_html(self, output_type):
        """"""
        html_path = self.get_html_path(output_type)
        if os.path.exists(html_path):
            webbrowser.open(f'file:///{html_path}')
            return True
        return False

    def save_settings(self, output_type, css_content, js_content):
        """CSS / JS"""
        self.config[f'obs_{output_type}_css'] = css_content
        self.config[f'obs_{output_type}_js'] = js_content
        self.save_config_callback()

    def load_settings(self, output_type):
        """CSS / JS"""
        css = self.config.get(f'obs_{output_type}_css', None)
        js = self.config.get(f'obs_{output_type}_js', None)
        return css, js

    def update_js_files(self):
        """
        HTMLJS
        CORS
        """
        import json
        
        for output_type in self.output_types:
            try:
                # 
                source_path = self.get_source_file_path(output_type)
                content = self.read_file_safe(source_path)
                
                # Format text to HTML before passing to JS
                formatted_content = self._format_text_to_html(content)
                
                # JS
                # updateContent("") 
                # json.dumps
                safe_content = json.dumps(formatted_content, ensure_ascii=False)
                js_content = f"if(typeof updateContent === 'function') {{ updateContent({safe_content}); }}"
                
                # JS
                js_path = os.path.join(self.project_root, 'output', f'obs_{output_type}_data.js')
                
                # I/O
                current_js_content = ""
                if os.path.exists(js_path):
                    with open(js_path, 'r', encoding='utf-8') as f:
                        current_js_content = f.read()
                
                if current_js_content != js_content:
                    with open(js_path, 'w', encoding='utf-8') as f:
                        f.write(js_content)
                        
            except Exception as e:
                print(f"Error updating JS file for {output_type}: {e}")
