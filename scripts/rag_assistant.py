#!/usr/bin/env python3
"""Closed-Loop Data Flow & Troubleshooting RAG Assistant.

Performs local semantic retrieval across all markdown documentation files
in the repository to help developers troubleshoot and review system data contracts.

Optional environment variables:
- OLLAMA_HOST: e.g. "http://localhost:11434" (default, if running)
- OPENAI_API_KEY: to use OpenAI GPT models
- GEMINI_API_KEY: to use Google Gemini models
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path


class DocumentChunk:
    def __init__(self, filepath: Path, header_chain: list[str], content: str, start_line: int, end_line: int):
        self.filepath = filepath
        self.header_chain = header_chain
        self.header_title = " > ".join(header_chain) if header_chain else "General"
        self.content = content.strip()
        self.start_line = start_line
        self.end_line = end_line

    def __repr__(self):
        return f"<Chunk {self.filepath.name} L{self.start_line}-{self.end_line}: {self.header_title}>"


def parse_markdown_file(filepath: Path) -> list[DocumentChunk]:
    """Parses a markdown file and splits it into chunks based on headers."""
    chunks = []
    current_headers = []
    current_content = []
    start_line = 1
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for idx, line in enumerate(lines, 1):
        # Match headers (e.g., # Header, ## Header, ### Header)
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            # Save previous chunk if it has content
            if current_content:
                chunks.append(
                    DocumentChunk(
                        filepath=filepath,
                        header_chain=list(current_headers),
                        content="".join(current_content),
                        start_line=start_line,
                        end_line=idx - 1
                    )
                )
                current_content = []

            # Update header chain based on level
            level = len(match.group(1))
            title = match.group(2).strip()
            
            # Keep header chain up to current level
            current_headers = current_headers[:level - 1]
            while len(current_headers) < level - 1:
                current_headers.append("")
            current_headers.append(title)
            
            start_line = idx
        
        current_content.append(line)

    # Save the last chunk
    if current_content:
        chunks.append(
            DocumentChunk(
                filepath=filepath,
                header_chain=list(current_headers),
                content="".join(current_content),
                start_line=start_line,
                end_line=len(lines)
            )
        )
        
    return chunks


def load_all_documents(repo_dir: Path) -> list[DocumentChunk]:
    """Recursively scans repository for markdown files and parses them."""
    all_chunks = []
    # Scan root files and docs directory
    targets = [repo_dir / "AGENTS.md", repo_dir / "README.md", repo_dir / "docs"]
    
    for target in targets:
        if not target.exists():
            continue
        if target.is_file() and target.suffix == ".md":
            all_chunks.extend(parse_markdown_file(target))
        elif target.is_dir():
            for md_file in target.rglob("*.md"):
                # Skip virtual environments or hidden folders
                if any(p in md_file.parts for p in (".venv", ".git", "__pycache__", "node_modules")):
                    continue
                all_chunks.extend(parse_markdown_file(md_file))
                
    return all_chunks


def tokenize(text: str) -> list[str]:
    """Simple tokenizer that splits words, lowercases, and filters out stopwords."""
    words = re.findall(r"\b\w{2,}\b", text.lower())
    stopwords = {
        "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", 
        "on", "at", "for", "with", "by", "about", "this", "that", "these", "those",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
        "的", "了", "和", "是", "就", "都", "在", "于", "及", "对", "以", "与", "或", "而"
    }
    return [w for w in words if w not in stopwords]


def retrieve_chunks(query: str, chunks: list[DocumentChunk], top_k: int = 3) -> list[tuple[float, DocumentChunk]]:
    """Retrieves top_k chunks using a pure-Python TF-IDF/BM25 scoring model."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # Calculate Document Frequency (DF) for IDF calculation
    df = {}
    for chunk in chunks:
        tokens = set(tokenize(chunk.header_title + " " + chunk.content))
        for token in tokens:
            df[token] = df.get(token, 0) + 1

    num_docs = len(chunks)
    scores = []

    for chunk in chunks:
        chunk_text = chunk.header_title + " " + chunk.content
        chunk_tokens = tokenize(chunk_text)
        chunk_words_set = set(chunk_tokens)
        
        score = 0.0
        for token in query_tokens:
            if token in chunk_words_set:
                # Term Frequency in chunk
                tf = chunk_tokens.count(token) / len(chunk_tokens)
                # Inverse Document Frequency (with smoothing)
                idf = math_log((num_docs + 1) / (df.get(token, 0) + 0.5))
                # Extra boost if query matches headers
                header_boost = 2.0 if any(token in h.lower() for h in chunk.header_chain) else 1.0
                score += tf * idf * header_boost
                
        if score > 0:
            scores.append((score, chunk))

    scores.sort(key=lambda x: x[0], reverse=True)
    return scores[:top_k]


def math_log(x: float) -> float:
    """Manual natural log implementation to avoid importing math if not needed."""
    # Simple Taylor series approximation or float implementation
    import math
    return math.log(x)


def query_ollama(prompt: str, host: str) -> str:
    """Helper to query local Ollama server if active."""
    url = f"{host.rstrip('/')}/api/generate"
    data = json.dumps({
        "model": "llama3", # default model, fallback to any if needed
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            resp = json.loads(res.read().decode("utf-8"))
            return resp.get("response", "").strip()
    except Exception as e:
        return f"Ollama connection error: {e}"


def query_openai(prompt: str, api_key: str) -> str:
    """Helper to query OpenAI API."""
    url = "https://api.openai.com/v1/chat/completions"
    data = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a professional robotics deployment assistant. Synthesize the provided context to answer the question precisely."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            resp = json.loads(res.read().decode("utf-8"))
            return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"OpenAI API error: {e}"


def run_llm_qa(query: str, matched_chunks: list[DocumentChunk]) -> str | None:
    """Attempts to synthesize an answer using LLM API if keys/servers are configured."""
    context = "\n\n".join([
        f"--- CONTEXT FROM: {c.filepath.name} (L{c.start_line}-L{c.end_line}) ---\nHeader: {c.header_title}\n{c.content}"
        for c in matched_chunks
    ])
    
    prompt = f"""Use the following retrieved context segments to answer the user's question. 
If the context does not contain the answer, explain what context is missing.
Keep your response concise, professional, and in Chinese.

[Context]
{context}

[Question]
{query}

[Answer]"""

    # 1. Try OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return query_openai(prompt, openai_key)
        
    # 2. Try Ollama (default local server)
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    # Check if local Ollama port is open
    try:
        with urllib.request.urlopen(ollama_host, timeout=1):
            return query_ollama(prompt, ollama_host)
    except Exception:
        pass
        
    return None


def main():
    repo_dir = Path(__file__).resolve().parents[1]
    print("=" * 60)
    print("🤖 三仓数据流与闭环调试 RAG 智能助手 🤖")
    print(f"正在扫描并向量化项目文档 (Repo: {repo_dir.name})...")
    
    chunks = load_all_documents(repo_dir)
    print(f"成功载入 {len(chunks)} 个文档段落。")
    print("=" * 60)
    print("提示：输入您想了解的数据契约、控制层或者故障排查问题（如 'PandaActionAdapter' 或 'Gate'）")
    print("按 'q' 键退出系统。\n")

    while True:
        try:
            query = input("👉 请输入您的问题: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not query:
            continue
        if query.lower() in ("q", "quit", "exit"):
            print("再见！")
            break

        # Semantic Retrieve
        results = retrieve_chunks(query, chunks, top_k=3)
        if not results:
            print("\n❌ 未找到相关文档匹配项，请尝试更换关键词。\n")
            continue

        print("\n🔍 【匹配到的参考段落】:")
        matched_chunks = []
        for rank, (score, chunk) in enumerate(results, 1):
            matched_chunks.append(chunk)
            file_link = f"file://{chunk.filepath.resolve()}#L{chunk.start_line}-L{chunk.end_line}"
            print(f"\n[{rank}] 评分: {score:.3f} | 章节: {chunk.header_title}")
            print(f"    📄 来源链接: [{chunk.filepath.name}]({file_link})")
            # Print a snippet of the content
            snippet = chunk.content[:250].replace("\n", "\n    ")
            print(f"    内容预览:\n    {snippet}...")

        # Optional LLM Synthesis
        print("\n🤖 【智能生成解答】:")
        answer = run_llm_qa(query, matched_chunks)
        if answer:
            print(answer)
        else:
            print("    [提示] 本地未检测到运行中的 Ollama 服务，且未配置 OPENAI_API_KEY。")
            print("    已为您定位到上述最相关的参考文档，您可以直接点击链接进行查阅。")
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
