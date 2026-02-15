import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 获取密钥
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PUSH_KEY = os.getenv('PUSH_KEY')

def fetch_abstract(arxiv_url):
    try:
        response = requests.get(arxiv_url, timeout=15)
        if response.status_code != 200: return "Error"
        soup = BeautifulSoup(response.text, 'html.parser')
        abstract_tag = soup.find('blockquote', class_='abstract mathjax')
        return abstract_tag.text.strip() if abstract_tag else "Error"
    except:
        return "Error"

def summarize_with_gemini(abstract_text):
    if not GEMINI_API_KEY: return "未配置 Gemini 密钥"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": f"请用中文简要总结以下摘要（1-2句）：\n\n{abstract_text}"}]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except:
        return "总结失败"

def fetch_papers_for_date_range(keyword, start_date, end_date, max_results):
    papers = []
    query = f'all:"{keyword}"'
    query_url = f"http://export.arxiv.org/api/query?search_query=({query})+AND+submittedDate:[{start_date}+TO+20261231235959]&start=0&max_results={max_results}"
    try:
        response = requests.get(query_url, timeout=15)
        root = ET.fromstring(response.content)
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
            summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()
            link_tag = entry.find('{http://www.w3.org/2005/Atom}link[@title="pdf"]')
            link = link_tag.attrib['href'] if link_tag is not None else ""
            papers.append({'title': title, 'summary': summary, 'link': link, 'keyword': keyword})
    except:
        pass
    return papers

if __name__ == "__main__":
    # 配置信息
    keywords = ["Two-stage robust optimization", "Industrial park power system", "UAV obstacle avoidance"]
    end_date = datetime.now().strftime("%Y%m%d%H%M%S")
    start_date = (datetime.now() - timedelta(days=2)).strftime("%Y%m%d%H%M%S")
    
    final_content = ""
    
    print(f"开始任务...")
    for kw in keywords:
        found_papers = fetch_papers_for_date_range(kw, start_date, end_date, 3)
        for paper in found_papers:
            summary = summarize_with_gemini(paper['summary'])
            item = f"【{paper['keyword']}】\n标题：{paper['title']}\n总结：{summary}\n链接：{paper['link']}\n\n"
            final_content += item
            time.sleep(2)

    # 写入结果文件
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(final_content if final_content else "今日无更新")

    # 推送逻辑
    if PUSH_KEY:
        title = f"每日文献速递-{datetime.now().strftime('%m/%d')}"
        if not final_content:
            desp = "☕ 报告老板：近两日你关注的领域暂无新论文发布。"
        else:
            desp = "💡 报告老板：今日最新论文总结如下：\n\n" + final_content.replace("\n", "\n\n")
        
        requests.post(f"https://sctapi.ftqq.com/{PUSH_KEY}.send", data={"title": title, "desp": desp})

    print("全部流程执行完毕")
