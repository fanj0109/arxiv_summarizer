import requests
import xml.etree.ElementTree as ET
import os
import time
from datetime import datetime, timedelta

# 1. 获取密钥
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
PUSH_KEY = os.environ.get('PUSH_KEY', '').strip()

def summarize_with_gemini(abstract):
    """极简调用，排除所有非必要参数"""
    # 强制尝试最通用的 v1 版本接口
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": f"请用中文总结这段摘要（1-2句）：\n\n{abstract}"}]}]}
    try:
        response = requests.post(url, json=payload, timeout=20)
        res_json = response.json()
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
        # 如果报错，把原始报错的前 30 个字发出来
        return f"总结失败：{str(res_json.get('error', {}).get('message', 'API无响应'))[:30]}"
    except:
        return "网络请求异常"

def fetch_papers(kw):
    """带基础容错的抓取"""
    # 实验模式：搜最近 7 天，确保有数据又不容易被封
    start = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d%H%M%S")
    url = f"http://export.arxiv.org/api/query?search_query=all:\"{kw}\"+AND+submittedDate:[{start}+TO+20261231235959]&max_results=2"
    try:
        r = requests.get(url, timeout=15)
        root = ET.fromstring(r.content)
        papers = []
        for e in root.findall('{http://www.w3.org/2005/Atom}entry'):
            title = e.find('{http://www.w3.org/2005/Atom}title').text.strip().replace('\n', ' ')
            summary = e.find('{http://www.w3.org/2005/Atom}summary').text.strip().replace('\n', ' ')
            link = e.find('{http://www.w3.org/2005/Atom}link[@title="pdf"]').attrib['href']
            papers.append({'title': title, 'summary': summary, 'link': link, 'kw': kw})
        return papers
    except:
        return []

if __name__ == "__main__":
    # 为了测试，我们用一个必然有论文的词
    keywords = ["Machine Learning", "Transformer"]
    final_content = ""
    
    print("开始抓取测试论文...")
    for kw in keywords:
        papers = fetch_papers(kw)
        print(f"关键词 【{kw}】 找到 {len(papers)} 篇")
        for p in papers:
            summary = summarize_with_gemini(p['summary'])
            final_content += f"【{p['kw']}】\n标题：{p['title']}\n总结：{summary}\n链接：{p['link']}\n\n"
            time.sleep(2)

    if PUSH_KEY:
        title = f"实验推送-{datetime.now().strftime('%m/%d')}"
        desp = "💡 推送实验结果：\n\n" + final_content if final_content else "今日无论文抓取"
        requests.post(f"https://sctapi.ftqq.com/{PUSH_KEY}.send", data={"title": title, "desp": desp})
    print("任务执行完毕")
