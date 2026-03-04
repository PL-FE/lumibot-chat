# 使用 Python 3.10 作为基础镜像（slim 版本以减小体积）
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 python 打印输出被缓冲，以及跳过交互
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=5001

# 安装系统依赖
# 包括构建可能需要的 gcc 库、以及网络代理和其他依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先仅拷贝 requirements.txt，以便利用 Docker 的缓存机制
COPY requirements.txt ./
COPY ai_strategy_web/requirements.txt ./ai_strategy_web/

# 安装项目依赖（主项目和Web项目）
# 先安装 lumibot 的依赖，再安装 web 的依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r ai_strategy_web/requirements.txt

# 将整个代码库拷贝进容器
COPY . .

# 如果项目本身是以一个包的方式运行或内部有依赖于包安装：
RUN pip install -e .

# 配置工作路径为 web 应用的目录，以便于运行 app.py
WORKDIR /app/ai_strategy_web

# 暴露端口，供外部访问（对应上面设定的 $PORT 或者 default 5001）
EXPOSE 5001

# 启动 Web 服务
CMD ["python", "app.py"]
