import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up your Gemini API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def fetch_abstract(arxiv_url):
    # Fetch the arXiv page content using requests
    response = requests.get(arxiv_url)
    if response.status_code != 200:
        return f"Error: Unable to fetch {arxiv_url}, status code: {response.status_code}"

    # Parse the HTML content of the arXiv page
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the abstract section
    abstract_tag = soup.find('blockquote', class_='abstract mathjax')
    if abstract_tag:
        # Get the content of the abstract and ensure a space after the "Abstract:" label
        abstract_text = abstract_tag.text.strip()
        # Ensure "Abstract:" has a space
        if abstract_text.startswith("Abstract:"):
            abstract_text = abstract_text.replace("Abstract:", "Abstract: ")
        return abstract_text
    else:
        return "Error: Abstract not found."

def summarize_with_gemini(abstract_text):
    # Set up the API endpoint for Gemini
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
    
    headers = {
        "Content-Type": "application/json",
    }

    # Create the payload to send the abstract to Gemini with a more focused prompt
    data = {
        "contents": [{
            "parts": [{
                "text": f"Summarize the following abstract in 1-2 simple sentences. Focus on what the authors did, why, and the results: \n\n{abstract_text}"
            }]
        }]
    }

    # Make the POST request to the Gemini API
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        # Extract the summary from the response
        result = response.json()
        try:
            # Access the correct keys in the response structure
            summary = result['candidates'][0]['content']['parts'][0]['text']
            return summary
        except KeyError as e:
            return f"KeyError: {e}, check the response structure."
    else:
        return f"Error: Unable to get response, status code: {response.status_code}"


def fetch_papers_for_date_range(keyword, start_date, end_date, max_results):
    papers = []
    query = f'all:"{keyword}"'
    query_url = f"http://export.arxiv.org/api/query?search_query=({query})+AND+submittedDate:[{start_date}+TO+{end_date}]&start=0&max_results={max_results}"
    
    # Fetch papers for this keyword and date range
    response = requests.get(query_url)
    if response.status_code != 200:
        print(f"Error: Unable to fetch papers for keyword '{keyword}' from {start_date} to {end_date}, status code: {response.status_code}")
        return papers

    # Parse the XML response to get the papers
    root = ET.fromstring(response.content)
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
        summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()
        link = entry.find('{http://www.w3.org/2005/Atom}link[@title="pdf"]').attrib['href']
        papers.append({'title': title, 'summary': summary, 'link': link, 'keyword': keyword})
    
    return papers

def fetch_papers(keywords, start_date, end_date, max_results_per_keyword):
    papers = []
    keyword_totals = {keyword: 0 for keyword in keywords}  # Dictionary to store total papers found for each keyword
    
    # Convert start_date and end_date to datetime objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Split the date range into monthly intervals
    current_start_date = start_date
    date_ranges = []
    while current_start_date < end_date:
        current_end_date = current_start_date + timedelta(days=30)  # Approximate 1 month
        if current_end_date > end_date:
            current_end_date = end_date
        date_ranges.append((current_start_date.strftime("%Y-%m-%d"), current_end_date.strftime("%Y-%m-%d")))
        current_start_date = current_end_date + timedelta(days=1)
    
    # Use ThreadPoolExecutor to parallelize queries
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for keyword in keywords:
            for start, end in date_ranges:
                futures.append(executor.submit(fetch_papers_for_date_range, keyword, start, end, max_results_per_keyword))
        
        for future in as_completed(futures):
            papers.extend(future.result())
    
    # Count papers per keyword
    for paper in papers:
        keyword_totals[paper['keyword']] += 1
    
    # Print the total number of documents found for each keyword
    print("\nTotal documents found per keyword:")
    for keyword, total in keyword_totals.items():
        print(f"{keyword}: {total} documents")
    
    return papers

# Open the result file to store the summaries
with open("result.txt", "w") as result_file:
   # --- 以下是修改后的自动化执行部分 ---

import os  # 确保你在文件最顶部已经 import os

# 1. 自动获取 Gemini 密钥（从 GitHub Secrets 读取）
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

with open("result.txt", "w", encoding="utf-8") as result_file:
    # 2. 直接写死你的关键词（不需要手动输入了）
    # 根据你的研究方向，我为你预设了以下关键词
    keywords = ["Two-stage robust optimization", "Industrial park power system", "UAV obstacle avoidance"]
    
    # 3. 自动计算日期范围（获取最近 2 天的论文，确保不遗漏）
    end_date_obj = datetime.now()
    start_date_obj = end_date_obj - timedelta(days=2)
    
    start_date = start_date_obj.strftime("%Y-%m-%d")
    end_date = end_date_obj.strftime("%Y-%m-%d")
    
    # 4. 设定每个关键词抓取的数量
    max_results_per_keyword = 5

    print(f"开始任务：抓取 {start_date} 至 {end_date} 的论文")

    # 获取论文列表
    papers = fetch_papers(keywords, start_date, end_date, max_results_per_keyword)
    
    if not papers:
        result_file.write("今日无相关关键词论文更新。")
        print("今日无更新。")
    
    for paper in papers:
        print(f"正在分析: {paper['title']}")
        
        # 获取摘要并调用 Gemini 总结
        abstract = paper['summary']
        if not abstract.startswith("Error"):
            summary = summarize_with_gemini(abstract)
            # 将结果写入文件
            output = f"关键词: {paper['keyword']}\n标题: {paper['title']}\n链接: {paper['link']}\nGemini 总结: {summary}\n\n"
            result_file.write(output)
            print(f"完成总结: {paper['title']}")
        else:
            result_file.write(f"标题: {paper['title']}\n错误: 无法获取摘要\n\n")
        
        # 稍微停顿，防止调用过快被封禁
        time.sleep(2)

print("今日论文自动阅读任务已完成，结果已保存至 result.txt")
