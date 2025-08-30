<div align="center">

中文 | [English](README_EN.md)

</div>

# 🚀 LaTeXTrans

> **基于多智能体协作的结构化LaTeX文档翻译系统, 将英文LaTeX文档翻译成中文PDF**



## ✨ 功能特点

> **使用大模型API直接翻译LaTeX源码，让翻译结果呈现与原文高度一致的排版**

## 🛠️ 安装指南

#### 1. 克隆仓库

```bash
git clone https://github.com/PolarisZZM/LaTeXTrans.git
cd LaTeXTrans
pip install -r requirements.txt
```

#### 2. 安装MikTex（推荐）或TeXLive

如需编译LaTeX文件（例如生成PDF输出），需要安装 [MikTex](https://miktex.org/download) 或 [TeXLive](https://www.tug.org/texlive/) !


## ⚙️ 配置说明


使用前请编辑配置文件：

```arduino
config/default.toml
```

设置语言模型的API密钥和基础URL：

```toml
[llm]
model = "deepseek-v3" #模型名称（可选）
api_key = " " #your_api_key_here
base_url = " " #base url of the API
```



## 📚 使用方式

### 🔹 通过ArXiv ID翻译（推荐）

只需提供arXiv论文ID即可完成翻译：

```bash
python main.py --arxiv (i.e. 2508.18791)
```

该命令将：

1. 从arXiv下载LaTeX源码
2. 解压到tex源文件目录
3. 运行多智能体翻译流程
4. 在outputs文件夹保存翻译后的.tex文件和编译的PDF


### 🔹 使用命令行运行

选项                | 功能                                                                                                      | 使用示例                                        |
| --------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `--config`            | Path to the config TOML file                        | `python main.py --config Path/config.toml`                                    |
| `--model`             | LLM for translating.                                | `python main.py --model deepseek-v3(e.g.)`                      |
| `--url`               | Model url                                           | `python main.py --url your url`                    |
| `--key`               | Model API key                                       | `python main.py --key your APIkey`                    |
| `--arxiv`             | Arxiv paper ID                                      | `python main.py --arxiv ****.*****`                  |


*首次启动时，你可以通过直接修改 config/default.toml 来启动。


## 💬 演示视频

系统演示视频： https://www.youtube.com/watch?v=tSVm_EOL7i8

## 🖼️ 翻译案例

以下是**LaTeXTrans**生成的三个真实翻译案例，左侧为原文，右侧为翻译结果。

### 📄 案例1：

<table>
  <tr>
    <td align="center"><b>原文</b></td>
    <td align="center"><b>译文</b></td>
  </tr>
  <tr>
    <td><img src="examples/case1src.png" width="100%"></td>
    <td><img src="examples/case1ch.png" width="100%"></td>
  </tr>
</table>

### 📄  案例2：

<table>
  <tr>
    <td align="center"><b>原文</b></td>
    <td align="center"><b>译文</b></td>
  </tr>
  <tr>
    <td><img src="examples/case2src.png" width="100%"></td>
    <td><img src="examples/case2ch.png" width="100%"></td>
  </tr>
</table>

### 📄 案例3：

<table>
  <tr>
    <td align="center"><b>原文</b></td>
    <td align="center"><b>译文</b></td>
  </tr>
  <tr>
    <td><img src="examples/case3src.png" width="100%"></td>
    <td><img src="examples/case3ch.png" width="100%"></td>
  </tr>
</table>

📂 **更多案例请查看[`examples/`](examples/) 文件夹**, 包含每个案例的完整翻译PDF。

---

