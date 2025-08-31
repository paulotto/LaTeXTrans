<div align="center">

[English](README.md) | 中文



#  LaTeXTrans：Structured LaTeX Translation with Multi-Agent Coordination

<p align="center">
  <a href="https://arxiv.org/abs/2503.06594" alt="paper"><img src="https://img.shields.io/badge/Paper-LaTeXTrans-blue?logo=arxiv&logoColor=white"/></a>
</p>

</div>

<div align="center">
<p dir="auto">

• 🛠️ [安装指南](#️-安装指南) 
• ⚙️ [配置说明](#️-配置说明)
• 📚 [使用方式](#-使用方式)
• 🖼️ [翻译案例](#️-翻译案例) 
</p>
</div>

 **LaTeXTrans 是一个基于多智能体协作的结构化 LaTeX 文档翻译系统, 该系统能够直接翻译 LaTeX 代码，并生成与原文排版高度一致的译文 PDF。LaTeXTrans 的主要应用场景为 arXiv 论文翻译，不同于传统文档翻译方法（例如 PDF 翻译）容易破坏公式和格式，该系统使用大模型直接翻译预处理过的论文 LaTeX 源码，并通过由 Parser, Translator, Validator, Summarizer, Terminology Extractor, Generator 这六个智能体组成的工作流实现了以下目标：**

 - <big>**保持公式、排版和交叉引用的完整性**</big>
 - <big>**保证术语翻译的一致性**</big>
 - <big>**支持从原文 LaTeX 源码到译文 PDF 的端到端转换**</big>

**借助 LaTeXTrans，研究人员和学生可以得到更高质量的论文翻译而无需担心格式混乱或内容缺失，从而更高效地阅读和理解 arXiv 论文。**

**下图展示了 LaTeXTrans 的系统架构，请阅读我们已经发布的论文 [LaTeXTrans: Structured LaTeX Translation with Multi-Agent Coordination](https://arxiv.org/abs/2508.18791) 以获得更详细的系统介绍。**


<img src="./main-figure.jpg" width="1000px"></img>


# 🛠️ 安装指南

#### 1. 克隆仓库

```bash
git clone https://github.com/PolarisZZM/LaTeXTrans.git
cd LaTeXTrans
pip install -r requirements.txt
```

#### 2. 安装MikTex（推荐, 更轻量）或TeXLive

如需编译LaTeX文件（例如生成PDF输出），需要安装 [MikTex](https://miktex.org/download) 或 [TeXLive](https://www.tug.org/texlive/) !

*对于 MikTex，安装时请务必选择 “install on the fly”，此外，您需要额外安装 [Strawberry Perl](http://strawberryperl.com/) 支持编译。


# ⚙️ 配置说明


使用前请编辑配置文件：

```arduino
config/default.toml
```

设置语言模型的API密钥和基础URL：

```toml
[llm]
model = "deepseek-v3" # 模型名称（可选）
api_key = " " # your_api_key_here
base_url = " " # base url of the API
```



# 📚 使用方式

### 🔹 通过 ArXiv ID 翻译（推荐）

只需提供 arXiv 论文 ID 即可完成翻译：

```bash
python main.py --arxiv {arxiv_paper_id}
# For example, 
# python main.py --arxiv 2508.18791
```

该命令将：

1. 从 arXiv 下载 LaTeX 源码
2. 解压到 tex 源文件目录
3. 运行多智能体翻译流程
4. 在 outputs 文件夹保存翻译后的论文 LaTeX 项目文件和编译生成的译文PDF


### 🔹 使用命令行运行

选项                | 功能                                                                                                      | 使用示例                                        |
| --------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `--model`             | LLM for translating                                | `python main.py --model deepseek-v3`                      |
| `--url`               | Model url                                           | `python main.py --url your url`                    |
| `--key`               | Model API key                                       | `python main.py --key your APIkey`                    |
| `--arxiv`             | arXiv paper ID                                      | `python main.py --arxiv 2508.18791`                  |


*首次启动时，你可以通过直接修改 config/default.toml 来启动。

*此版本暂时只支持英文到中文的翻译


# 🖼️ 翻译案例

以下是 **LaTeXTrans** 生成的三个真实翻译案例，左侧为原文，右侧为翻译结果。

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

📂 **更多案例请查看[`examples/`](examples/) 文件夹**, 包含每个案例的完整翻译 PDF。

---

## Citation
```bash
@misc{zhu2025latextransstructuredlatextranslation,
      title={LaTeXTrans: Structured LaTeX Translation with Multi-Agent Coordination}, 
      author={Ziming Zhu and Chenglong Wang and Shunjie Xing and Yifu Huo and Fengning Tian and Quan Du and Di Yang and Chunliang Zhang and Tong Xiao and Jingbo Zhu},
      year={2025},
      eprint={2508.18791},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2508.18791}, 
}
```