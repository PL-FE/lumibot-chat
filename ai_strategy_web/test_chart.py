import io
import base64
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC', 'sans-serif']

def generate_placeholder_chart() -> str:
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    ax.text(0.5, 0.5, "图表数据暂不可用", transform=ax.transAxes,
            ha="center", va="center", color="#aaaacc", fontsize=16)
    ax.set_axis_off()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

c = generate_placeholder_chart()
print("Placeholder length:", len(c))
