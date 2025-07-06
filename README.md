
# 🚀 LaTeXTrans

> **A structured LaTeX document translation system based on multi-agent collaboration**


---

## ✨ Features

- 🧠 **Multi-agent collaboration**: Parser, Translator, Summarizer, Terminology Extractor, Generator  
- 📄 **LaTeX-aware structure preservation**: Retains `\section`, `\label`, `\ref`, environments, math, and formatting  
- 🌐 **Flexible backend support**: Works with GPT-4, DeepSeek, or your own LLM API  
- 📚 **ArXiv ID support**: Automatically downloads and translates papers from arXiv with a single command  
- 🧰 **Customizable pipeline**: Easily adjust summarization, terminology injection, and translation agents  

---

## 🛠️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/PolarisZZM/LaTeXTrans.git
cd LaTeXTrans
pip install -r requirements.txt
```

### 2. Install TeXLive

To compile LaTeX files (e.g., generating PDF output), you need to install [TeXLive](https://www.tug.org/texlive/).

## ⚙️ Configuration

Before using the system, open the configuration file:

```arduino
config/default.toml
```


And set your API key and base URL for the language model:

```toml
[llm]
api_key = " " #your_api_key_here
base_url = " " #base url of the API
```

You can connect to services such as OpenAI, DeepSeek, Claude, or your own hosted LLMs that follow the OpenAI-compatible API format.

## 🚀 Usage

### 🔹 Run with ArXiv ID (recommended)

You can translate an arXiv paper by simply passing its ID:

```bash
python main.py <paper_id> (i.e. 2501.12948)
```

This will:

Download the LaTeX source from arXiv

Unpack the source into the tex cource folder

Run the multi-agent translation pipeline

Save the translated .tex file and the compiled PDF in the outputs folder

## 💬 Demonstration video

The demonstration video of our system: https://www.youtube.com/watch?v=tSVm_EOL7i8