
# Script for generating the Python protobuf structures
## Disclaimer: All code in this repository is for learning, research, and exchange only. It must not be used for illegal or harmful purposes, including but not limited to commercial profit, system sabotage, or stealing personal information. Any consequences arising from violating this disclaimer are borne by the violator.
## For infringement or related-interest issues, contact the author: [Weibo](https://weibo.com/u/7751075499), [Bilibili](https://space.bilibili.com/4690313), [Email](mailto:kukushka@126.com)
> January 2, 2024

## 0. Install [betterproto](https://github.com/danielgtaylor/python-betterproto)
```shell
pip install betterproto
```
Note: the `betterproto` version is `2.0.0b6`; it must be 2.0 or above.
## 1. Open a terminal in the current directory and run:
```shell
protoc -I . --python_betterproto_out=. douyin.proto
```
If `douyin.py` and `__init__.py` are generated in the current directory, it succeeded (they have already been generated and are ready to use).

## Done