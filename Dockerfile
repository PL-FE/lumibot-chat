# 使用 Python 3.10 作为基础镜像（slim 版本以减小体积）
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 python 打印输出被缓冲，以及跳过交互
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=5001

# 为了解决国内网络访问 deb.debian.org 慢或者超时的问题，配置清华源。
# 同时处理了 debian 12+ (bookworm) 采用 debian.sources 格式的情况。
RUN rm -f /etc/apt/sources.list.d/debian.sources && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 更新包列表并安装所需系统依赖
RUN apt-get clean && apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先仅拷贝 requirements.txt，以便利用 Docker 的缓存机制
COPY requirements.txt ./
COPY ai_strategy_web/requirements.txt ./ai_strategy_web/

# 安装项目依赖（主项目和Web项目）
# 先安装 lumibot 的依赖，再安装 web 的依赖
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --default-timeout=100 && \
    pip install --no-cache-dir -r ai_strategy_web/requirements.txt --default-timeout=100

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
