import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. 自动获取 Gemini 密钥（从 GitHub Secrets 读取）
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def fetch_abstract(arxiv_url):
    response = requests.get(arxiv_url)
    if response.status_code != 200:
        return f"Error: Unable to fetch {arxiv_url}, status code: {response.status_code}"
    soup = BeautifulSoup(response.text, 'html.parser')
    abstract_tag = soup.find('blockquote', class_='abstract mathjax')
    if abstract_tag:
        abstract_text = abstract_tag.text.strip()
        if abstract_text.startswith("Abstract:"):
            abstract_text = abstract_text.replace("Abstract:", "Abstract: ")
        return abstract_text
    else:
        return "Error: Abstract not found."

def summarize_with_gemini(abstract_text):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + (GEMINI_API_KEY or "")
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{
                "text": f"请用中文简要总结以下论文摘要（1-2句话）。重点说明作者做了什么、为什么做以及主要结果: \n\n{abstract_text}"
            }]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            summary = result['candidates'][0]['content']['parts'][0]['text']
            return summary
        else:
            return f"Error: API 返回错误代码 {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

def fetch_papers_for_date_range(keyword, start_date, end_date, max_results):
    papers = []
    query = f'all:"{keyword}"'
    query_url = f"http://export.arxiv.org/api/query?search_query=({query})+AND+submittedDate:[{start_date}+TO+{end_date}]&start=0&max_results={max_results}"
    response = requests.get(query_url)
    if response.status_code != 200:
        return papers
    root = ET.fromstring(response.content)
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
        summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()
        link_tag = entry.find('{http://www.w3.org/2005/Atom}link[@title="pdf"]')
        link = link_tag.attrib['href'] if link_tag is not None else "No Link"
        papers.append({'title': title, 'summary': summary, 'link': link, 'keyword': keyword})
    return papers

def fetch_papers(keywords, start_date, end_date, max_results_per_keyword):
    papers = []
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_papers_for_date_range, kw, start_date, end_date, max_results_per_keyword) for kw in keywords]
        for future in as_completed(futures):
            papers.extend(future.result())
    return papers

# --- 主程序执行部分 ---
if __name__ == "__main__":
    # 2. 设定你的关键词
    keywords = ["Two-stage robust optimization", "Industrial park power system", "UAV","GRN","swarm"]
    
    # 3. 自动计算日期范围
    end_date_obj = datetime.now()
    start_date_obj = end_date_obj - timedelta(days=2)
    start_date = start_date_obj.strftime("%Y-%m-%d")
    end_date = end_date_obj.strftime("%Y-%m-%d")
    
    max_results_per_keyword = 5

    with open("result.txt", "w", encoding="utf-8") as result_file:
        print(f"开始任务：抓取 {start_date} 至 {end_date} 的论文")
        papers = fetch_papers(keywords, start_date, end_date, max_results_per_keyword)
        
        if not papers:
            result_file.write("今日无相关关键词论文更新。")
        
        for paper in papers:
            print(f"正在分析: {paper['title']}")
            abstract = paper['summary']
            summary = summarize_with_gemini(abstract)
            
            output = f"关键词: {paper['keyword']}\n标题: {paper['title']}\n链接: {paper['link']}\n总结: {summary}\n\n"
            result_file.write(output)
            time.sleep(2) # 避免请求过快

# --- 在文件最末尾添加以下内容 ---
    # 读取推送钥匙
    push_key = os.getenv('PUSH_KEY')
    if push_key:
        import requests
        # 读取刚刚写好的结果文件内容
        with open("result.txt", "r", encoding="utf-8") as f:
           # --- 任务结束，开始处理推送逻辑 ---
    push_key = os.getenv('PUSH_KEY')
    if push_key:
        import requests
        print("正在准备发送微信通知...")
        
        # 1. 读取抓取到的结果
        with open("result.txt", "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        # 2. 如果文件为空或内容太短，说明没抓到论文
        if not content or len(content) < 5:
            title = f"今日论文提醒：暂无更新 ({datetime.now().strftime('%m/%d')})"
            desp = "☕ 报告老板：在你关注的科研领域（两阶段鲁棒优化/电力系统/无人机），近两日 ArXiv 暂无新论文发布。享受没有文献压力的一天吧！"
        else:
            title = f"今日论文速递 - {datetime.now().strftime('%m/%d')}"
            desp = "💡 报告老板：Gemini 已为你读完以下最新文献：\n\n" + content.replace("\n", "\n\n")

        # 3. 发送至 Server酱
        push_url = f"https://sctapi.ftqq.com/{push_key}.send"
        data = {
            "title": title,
            "desp": desp
        }
        
        try:
            res = requests.post(push_url, data=data)
            print(f"微信接口返回: {res.text}")
        except Exception as e:
            print(f"发送失败: {e}")

print("全部流程已执行完毕。")
