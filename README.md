<div align="center">

English | [中文](README_ZH.md)

#  LaTeXTrans：Structured LaTeX Translation with Multi-Agent Coordination

<p align="center">
  <a href="https://arxiv.org/abs/2503.06594" alt="paper"><img src="https://img.shields.io/badge/Paper-LaTeXTrans-blue?logo=arxiv&logoColor=white"/></a>
</p>

</div>

<div align="center">
<p dir="auto">

• 🛠️ [Installation Guide](#️-installation-guide) 
• ⚙️ [Configuration Guide](#️-configuration-guide)
• 📚 [Usage](#-Usage)
• 🖼️ [Translation Examples](#️-translation-examples) 

</p>
</div>

**LaTeXTrans is a structured LaTeX document translation system based on multi-agent collaboration. It directly translates LaTeX code and generates translated PDFs with high fidelity to the original layout. The primary application of LaTeXTrans is *<big>*arXiv paper translation*</big>*. Unlike traditional document translation methods (e.g., PDF translation), which often break formulas and formatting, LaTeXTrans leverages LLM to translate preprocessed LaTeX sources and employs a workflow composed of six agents—Parser, Translator, Validator, Summarizer, Terminology Extractor, and Generator—to achieve the following goals:**

 - *<big>***Preserve the integrity of formulas, layout, and cross-references***</big>*
 - *<big>***Ensure consistency in terminology translation***</big>*
 - *<big>***Support end-to-end conversion from original LaTeX source to translated PDF***</big>*

**With LaTeXTrans, researchers and students can obtain higher-quality paper translations without worrying about formatting confusion or missing content, thus reading and understanding arXiv papers more efficiently.**

**The figure below illustrates the system architecture of LaTeXTrans. For a more detailed introduction, please refer to our published paper [LaTeXTrans: Structured LaTeX Translation with Multi-Agent Coordination](https://arxiv.org/abs/2508.18791).**

<img src="./main-figure.jpg" width="1000px"></img>

# 🛠️ Installation Guide

#### 1. Clone Repository

```bash
git clone https://github.com/PolarisZZM/LaTeXTrans.git
cd LaTeXTrans
pip install -r requirements.txt
```

#### 2. Install MikTex(Recommended) or TeXLive

If you need to compile LaTeX files (e.g., generate PDF output), install [MikTex](https://miktex.org/download) or [TeXLive](https://www.tug.org/texlive/) !

*For MikTex, installation please be sure to select "install on the fly", in addition, you need to install additional [Strawberry Perl](http://strawberryperl.com/) support compilation.

# ⚙️ Configuration Guide

### Local Configuration

Please edit the configuration file before use:

```arduino
config/default.toml
```

Set the language model's API key and base URL:

```toml
[llm]
model = "deepseek-v3" # model name (optional)
api_key = " " # your_api_key_here
base_url = " " # base url of the API
```


# 📚 Usage

### 🔹 Translation via ArXiv ID (Recommended)

Simply provide an arXiv paper ID to complete translation:

```bash
python main.py --arxiv {arxiv_paper_id}
# For example, 
# python main.py --arxiv 2508.18791
```

This command will:

1. Download LaTeX source code from arXiv
2. Extract to tex source file directory
3. Run multi-agent translation workflow
4. Save the translated LaTeX project file of the paper and the PDF of the compiled translation in the outputs folder


### 🔹 Running with CLI

| Option                | Function                                                                                                      | Example                                        |
| --------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `--model`             | LLM for translating                                | `python main.py --model deepseek-v3`                      |
| `--url`               | Model url                                           | `python main.py --url your url`                    |
| `--key`               | Model API key                                       | `python main.py --key your APIkey`                    |
| `--arxiv`             | arXiv paper ID                                      | `python main.py --arxiv 2508.18791`                  |


*For initial setup, users may launch the system by directly modifying the config/default.toml file.

*This version currently only supports translation from English to Chinese


# 🧰 Experimental Results

| System | COMETkiwi | LLM-score | FC-score | Cost |
|:-|:-:|:-:|:-:|:-:|
|NiuTrans |64.69|7.93|60.72|-|
|Google Translate |46.23|5.93|51.00|-|
|LLaMA-3.1-8b|42.89|2.92|49.40|-|
|Qwen-3-8b|45.55|7.87|48.68|-|
|Qwen-3-14b|68.18|8.76|65.63|-|
|DeepSeek-V3|67.26|9.02|63.68|$0.02|
|GPT-4o|67.22|8.58|58.32|$0.13|
|**LaTeXTrans(Qwen-3-14b)**|71.37|8.97|71.20|-|
|**LaTeXTrans(DeepSeek-V3)**|73.48|9.01|70.52|$0.10|
|**LaTeXTrans(GPT-4o)**|73.59|8.92|71.52|$0.35|

Note:
- **COMETkiwi** : a quality estimation model that reflects the quality of the translation, the higher the score, the better the translation quality.
- **LLM-score** : a method for evaluating the quality of translation using LLM (GPT-4o), the higher the score, the better the translation quality.
- **FC-score** : a method proposed in our paper to evaluate the formatting ability of LaTeX translation by detecting the number of errors in the compiled logs, the higher the score, the better the ability to maintain format.
- **Cost** : the cost incurred when using the official API to translate each paper on average in the test set.
  


# 🖼️ Translation Examples

The following are three real translation examples generated by **LaTeXTrans**, with the original text on the left and translation results on the right.

### 📄 Case 1:

<table>
  <tr>
    <td align="center"><b>Original</b></td>
    <td align="center"><b>Translation</b></td>
  </tr>
  <tr>
    <td><img src="examples/case1src.png" width="100%"></td>
    <td><img src="examples/case1ch.png" width="100%"></td>
  </tr>
</table>

### 📄 Case 2:

<table>
  <tr>
    <td align="center"><b>Original</b></td>
    <td align="center"><b>Translation</b></td>
  </tr>
  <tr>
    <td><img src="examples/case2src.png" width="100%"></td>
    <td><img src="examples/case2ch.png" width="100%"></td>
  </tr>
</table>

### 📄 Case 3:

<table>
  <tr>
    <td align="center"><b>Original</b></td>
    <td align="center"><b>Translation</b></td>
  </tr>
  <tr>
    <td><img src="examples/case3src.png" width="100%"></td>
    <td><img src="examples/case3ch.png" width="100%"></td>
  </tr>
</table>

📂 **See [`examples/`](examples/) folder for more cases**, including complete translation PDFs for each case.

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