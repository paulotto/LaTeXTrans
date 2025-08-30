<div align="center">

中文 | [English](README_EN.md)



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

 **LaTeXTrans 是一个基于多智能体协作的结构化 LaTeX 文档翻译系统, 该系统使用大模型直接翻译预处理过的 LaTeX 源码，通过由 Parser, Translator, Validator, Summarizer, Terminology Extractor, Generator 这六个智能体组成的工作流确保格式保持、排版一致性、引用跳转和术语一致性，并且实现从原文 LaTeX源码到译文PDF的端到端翻译。请阅读我们已经发布的论文 [LaTeXTrans: Structured LaTeX Translation with Multi-Agent Coordination](https://arxiv.org/abs/2508.18791) 以获得更详细的系统介绍。**

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

*对于 MikTex，安装时请务必选择 install on the fly，此外，您需要额外安装 [Strawberry Perl](http://strawberryperl.com/) 支持编译。


# ⚙️ 配置说明


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



# 📚 使用方式

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

*此版本暂时只支持英文到中文的翻译


# 💬 演示视频

系统演示视频： https://www.youtube.com/watch?v=tSVm_EOL7i8

## 🧰 实验结果

| System | Cometkiwi | LLM-score | FC-score | Cost |
|:-|:-:|:-:|:-:|:-:|
|[NiuTrans](https://niutrans.com/trans?type=text) |64.69|7.93|60.72|-|
|Google Translate |46.23|5.93|51.00|-|
|LLaMA-3.1-8b|42.89|2.92|49.40|-|
|Qwen-3-8b|45.55|7.87|48.68|-|
|Qwen-3-14b|68.18|8.76|65.63|-|
|DeepSeek-V3|67.26|9.02|63.68|$0.02|
|GPT-4o|67.22|8.58|58.32|$0.13|
|**LaTeXTrans(Qwen-3-14b)**|71.37|8.97|71.20|-|
|**LaTeXTrans(DeepSeek-V3)**|73.48|9.01|70.52|$0.10|
|**LaTeXTrans(GPT-4o)**|73.59|8.92|71.52|$0.35|


# 🖼️ 翻译案例

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