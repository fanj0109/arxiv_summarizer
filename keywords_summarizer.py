import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time
import os
from datetime import datetime, timedelta

# 1. 获取密钥（增加 strip 确保没有空格）
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
PUSH_KEY = os.environ.get('PUSH_KEY', '').strip()

def summarize_with_gemini(text_to_summarize):
    """调用 Gemini 进行总结 - 官方标准 REST 格式版"""
    if not GEMINI_API_KEY:
        return "【错误】未发现 GEMINI_API_KEY"

    # 官方标准格式：https://generativelanguage.googleapis.com/{version}/{model_path}:generateContent
    # 注意：model_path 必须包含 "models/" 前缀
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    
    # 构造最简化的请求体
    payload = {
        "contents": [{
            "parts": [{
                "text": f"请用中文简要总结以下论文摘要（1-2句）：\n\n{text_to_summarize}"
            }]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        # 1. 成功获取
        if 'candidates' in result and len(result['candidates']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # 2. 捕捉具体的 API 错误
        if 'error' in result:
            error_code = result['error'].get('code')
            error_msg = result['error'].get('message')
            print(f"Gemini API 报错 ({error_code}): {error_msg}")
            
            # 如果是模型找不到，尝试一个绝对稳健的备选路径
            if "not found" in error_msg.lower():
                alt_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
                alt_res = requests.post(alt_url, headers=headers, json=payload, timeout=30).json()
                if 'candidates' in alt_res:
                    return alt_res['candidates'][0]['content']['parts'][0]['text'].strip()
            
            return f"总结失败: {error_msg}"
            
        return "总结失败：返回格式未知"
        
    except Exception as e:
        return f"网络调用异常: {str(e)}"

def fetch_papers_with_retry(keyword, start_date, end_date):
    """带重试功能的抓取"""
    query = f'all:"{keyword}"'
    query_url = f"http://export.arxiv.org/api/query?search_query=({query})+AND+submittedDate:[{start_date}+TO+20261231235959]&start=0&max_results=3"
    
    for attempt in range(3):
        try:
            print(f"正在抓取 【{keyword}】 (第 {attempt+1} 次尝试)...")
            response = requests.get(query_url, timeout=30)
            if response.status_code == 200:
                # 检查返回的是不是 XML (如果是被封锁，返回的是 HTML，第一位不是 <)
                if not response.text.strip().startswith('<'):
                    print(f"ArXiv 返回了非 XML 数据（可能是封锁页面），等待重试...")
                    time.sleep(15)
                    continue
                
                root = ET.fromstring(response.content)
                papers = []
                for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                    title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip().replace('\n', ' ')
                    summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip().replace('\n', ' ')
                    link_tag = entry.find('{http://www.w3.org/2005/Atom}link[@title="pdf"]')
                    link = link_tag.attrib['href'] if link_tag is not None else ""
                    papers.append({'title': title, 'summary': summary, 'link': link, 'keyword': keyword})
                return papers
            elif response.status_code == 503:
                time.sleep(20)
        except Exception as e:
            print(f"尝试失败: {e}")
            time.sleep(10)
    return []

if __name__ == "__main__":
    # 使用热门词进行实验
    keywords = ["Machine Learning", "Transformer", "UAV"]
    # 搜索最近 30 天
    end_date = datetime.now().strftime("%Y%m%d%H%M%S")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d%H%M%S")
    
    final_content = ""
    for kw in keywords:
        found = fetch_papers_with_retry(kw, start_date, end_date)
        for paper in found:
            summary = summarize_with_gemini(paper['summary'])
            final_content += f"【{paper['keyword']}】\n标题：{paper['title']}\n总结：{summary}\n链接：{paper['link']}\n\n"
            time.sleep(2)

    # --- 实验模式核心：如果没有论文，也强行测一次 Gemini ---
    if not final_content:
        test_summary = summarize_with_gemini("This is a test message to verify if the Gemini API Key is working correctly.")
        final_content = f"⚠️ 今日未抓取到论文（可能被 ArXiv 暂时封锁）。\n\nGemini 密钥测试结果：{test_summary}"

    # 发送推送
    if PUSH_KEY:
        title = f"实验模式推送-{datetime.now().strftime('%m/%d')}"
        requests.post(f"https://sctapi.ftqq.com/{PUSH_KEY}.send", data={"title": title, "desp": final_content.replace("\n", "\n\n")})

    print("实验模式运行完毕")
