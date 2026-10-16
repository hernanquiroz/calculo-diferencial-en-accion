
# app.py — Solucionador de Cálculo Diferencial paso a paso (Streamlit + SymPy + Matplotlib)
# ---------------------------------------------------------------------------
# Despliegue en Streamlit Cloud (gratis, conectado a GitHub):
#   1. Sube este archivo como app.py a un repositorio de GitHub
#   2. Añade un archivo requirements.txt con:
#        streamlit
#        sympy
#        matplotlib
#      (y opcionalmente un README.md)
#   3. Entra a https://share.streamlit.io → "New app" → selecciona el repo
#      → rama main → archivo app.py → Deploy. Listo: URL pública en ~2 min.
#
# Ejecución local:  streamlit run app.py
# ---------------------------------------------------------------------------

import time
import traceback

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
import sympy as sp
from sympy import sympify, latex

matplotlib.use("Agg")

x = sp.Symbol("x")


# ===================== UTILIDADES =====================
@st.cache_data(show_spinner=False)
def parse_fn(src: str):
    """Convierte el texto del usuario en una expresión SymPy."""
    src = src.replace("−", "-").replace("π", "pi").replace("^", "**")
    return sympify(src, locals={"e": sp.E})


def derivative_steps(f, depth=0, steps=None):
    """
    Derivada recursiva QUE GENERA PASOS (los pasos se propagan a la lista raíz).
    Devuelve (derivada_simbolica, lista_de_pasos).
    """
    if steps is None:
        steps = []

    def rule_line(r, expr):
        steps.append((r, sp.simplify(expr) if expr is not None else None))

    def D(g):
        return derivative_steps(g, depth + 1, steps)[0]

    if f.is_Number:
        rule_line("Regla de la constante: (c)′ = 0", sp.Integer(0))
        return sp.Integer(0), steps

    if f == x:
        rule_line("Regla de la identidad: (x)′ = 1", sp.Integer(1))
        return sp.Integer(1), steps

    if isinstance(f, sp.Symbol):
        rule_line("Derivada respecto a x de una constante = 0", sp.Integer(0))
        return sp.Integer(0), steps

    # ---- Suma / Resta ----
    if isinstance(f, sp.Add):
        args = f.as_ordered_terms()
        rule_line(
            "Regla de la suma: la derivada de una suma es la suma de las derivadas",
            sum(D(a) for a in args),
        )
        return sum(D(a) for a in args), steps

    # ---- Producto: u·v ----
    if isinstance(f, sp.Mul):
        c, rest = f.as_independent(x)
        if rest.has(x):
            if not c == 1:  # constante · función
                rule_line(
                    f"Regla del producto con constante: ({sp.latex(c)}·g)′ = {sp.latex(c)}·g′",
                    c * D(rest),
                )
                return c * D(rest), steps
            # producto genuino de dos factores con x
            factors = [a for a in f.args if a.has(x)]
            u, v = factors[0], sp.Mul(*factors[1:])
            du, dv = D(u), D(v)
            rule_line(
                "Regla del producto: (u·v)′ = u′·v + u·v′",
                du * v + u * dv,
            )
            return du * v + u * dv, steps

    # ---- Cociente ----
    if isinstance(f, sp.Pow) and f.exp == -1 and f.base.has(x):
        v = f.base
        rule_line(
            "Regla del recíproco: (1/v)′ = −v′/v²",
            -D(v) / v**2,
        )
        return -D(v) / v**2, steps

    # ---- Potencia u^n ----
    if isinstance(f, sp.Pow) and not f.exp.has(x):
        u, n = f.base, f.exp
        du = D(u)
        result = n * u ** (n - 1)
        if u == x:
            rule_line(f"Regla de la potencia: (x^{n})′ = {n}·x^({n}−1)", result)
        else:
            rule_line(
                f"Potencia + regla de la cadena: (u^{n})′ = {n}·u^({n}−1)·u′  con u = {u}",
                result * du,
            )
            result = result * du
        return result, steps

    # ---- Exponencial a^v ----
    if isinstance(f, sp.Pow) and not f.base.has(x) and f.exp.has(x):
        a, v = f.base, f.exp
        dv = D(v)
        if a == sp.E:
            rule_line(f"Exponencial natural: (e^v)′ = e^v·v′  con v = {v}", f * dv)
        else:
            rule_line(f"Exponencial: ({a}^v)′ = {a}^v·ln({a})·v′  con v = {v}", f * sp.ln(a) * dv)
        return f * (sp.ln(a) if a != sp.E else 1) * dv, steps

    # ---- Funciones elementales (con cadena) ----
    TABLE = {
        sp.sin: ("(sen u)′ = cos(u)·u′", lambda u, du: sp.cos(u) * du),
        sp.cos: ("(cos u)′ = −sen(u)·u′", lambda u, du: -sp.sin(u) * du),
        sp.tan: ("(tan u)′ = sec²(u)·u′ = u′/cos²(u)", lambda u, du: du / sp.cos(u) ** 2),
        sp.exp: ("(e^u)′ = e^u·u′", lambda u, du: sp.exp(u) * du),
        sp.log: ("(ln u)′ = u′/u", lambda u, du: du / u),
        sp.sqrt: ("(√u)′ = u′/(2√u)", lambda u, du: du / (2 * sp.sqrt(u))),
        sp.asin: ("(arcsen u)′ = u′/√(1−u²)", lambda u, du: du / sp.sqrt(1 - u**2)),
        sp.acos: ("(arccos u)′ = −u′/√(1−u²)", lambda u, du: -du / sp.sqrt(1 - u**2)),
        sp.atan: ("(arctan u)′ = u′/(1+u²)", lambda u, du: du / (1 + u**2)),
        sp.sinh: ("(senh u)′ = cosh(u)·u′", lambda u, du: sp.cosh(u) * du),
        sp.cosh: ("(cosh u)′ = senh(u)·u′", lambda u, du: sp.sinh(u) * du),
        sp.tanh: ("(tanh u)′ = u′·(1−tanh²u)", lambda u, du: du * (1 - sp.tanh(u) ** 2)),
        sp.Abs: ("(|u|)′ = u′·sign(u)", lambda u, du: du * sp.sign(u)),
    }
    if f.func in TABLE and len(f.args) == 1:
        u = f.args[0]
        du = D(u)
        name, rule = TABLE[f.func]
        if u == x:
            steps.append((f"Regla directa: {name.replace('u', 'x')}", rule(u, du)))
        else:
            steps.append((f"{name}  — regla de la cadena con u = {u}", rule(u, du)))
        return rule(u, du), steps

    # Fallback: SymPy resuelve y lo anunciamos (sin regla reconocida)
    result = sp.diff(f, x)
    steps.append(("Regla compuesta avanzada — SymPy la deriva directamente", result))
    return result, steps


@st.cache_data(show_spinner=False)
def full_analysis(f):
    df = sp.diff(f, x)
    ddf = sp.diff(f, x, 2)
    return sp.simplify(df), sp.simplify(ddf)


def fnum(f):
    """Convierte la expresión a una función numpy rápida."""
    return sp.lambdify(x, f, modules=["numpy"])


def fmt_val(v):
    try:
        v = float(v)
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.4g}"
    except (TypeError, ValueError):
        return str(v)


# ===================== TERMINAL CON EFECTO DE TECLEO =====================
# La terminal se renderiza como HTML AUTOCONTENIDO dentro de un iframe (st.iframe),
# que NO pasa por el sanitizador de st.markdown: el CSS siempre se aplica.

TERM_HEIGHT = 460  # altura fija de la ventana de terminal (px)

# CSS de la terminal. OJO: se concatena la altura; NO usar formateo % aquí
# porque el CSS contiene literales "50%" que romperían el formateo.
_TERM_CSS = (
    """
<style>
  body { margin:0; background:transparent; font-family:'JetBrains Mono','Cascadia Code',Consolas,monospace; }
  .terminal { background:#05070d; border:1px solid #1e2a3d; border-radius:14px;
              box-shadow:0 12px 40px rgba(0,0,0,.55); overflow:hidden; }
  .term-head { display:flex; align-items:center; gap:8px; padding:10px 14px;
               background:#0d1322; border-bottom:1px solid #1e2a3d; }
  .dot { width:12px; height:12px; border-radius:50%; }
  .d1{background:#ff5f57}.d2{background:#febc2e}.d3{background:#28c840}
  .term-title { margin-left:10px; color:#8b949e; font-size:.78rem; }
  .term-body { padding:16px 18px; font-size:.86rem; line-height:1.85;
               overflow-y:auto; white-space:pre-wrap; }
  .cursor { display:inline-block; width:9px; height:1.05em; background:#3fb950;
            vertical-align:text-bottom; animation:blink 1s steps(1) infinite; }
  @keyframes blink { 50% { opacity:0; } }
  .tl { color:#e3b341; font-weight:600; }
  .tr { color:#3fb950; }
  .tn { color:#7d8590; font-style:italic; }
  .te { color:#f85149; }
</style>
"""
)


def type_terminal(lines, speed_ms):
    """Escribe línea por línea dentro de la terminal macOS, con cursor parpadeante."""
    for i in range(len(lines) + 1):
        shown = lines[:i]
        body = "".join(render_line(k, t) for k, t in shown)
        cursor = '<span class="cursor"></span>' if i < len(lines) else ""
        terminal_html(body + cursor)
        if i < len(lines):
            time.sleep((speed_ms / 1000.0) * 3)


def terminal_html(body):
    with TERM_BOX:
        # ⚠️ CORRECCIÓN: en Streamlit 1.66+ el parámetro `scrolling` fue removido.
        # Solo se admite `body` (HTML), `width` y `height`.
        st.iframe(
            _TERM_CSS
            + f"""
            <div class="terminal" style="height:{TERM_HEIGHT}px;">
              <div class="term-head">
                <div class="dot d1"></div><div class="dot d2"></div><div class="dot d3"></div>
                <span class="term-title">calcdiff — bash</span>
              </div>
              <div class="term-body" style="height:{TERM_HEIGHT - 46}px;">{body}</div>
            </div>
            <script>
              const b = document.querySelector('.term-body');
              if (b) b.scrollTop = b.scrollHeight;
            </script>
            """,
            height=TERM_HEIGHT,
        )


def render_line(kind, text):
    cls = {"title": "tl", "result": "tr", "note": "tn", "err": "te"}.get(kind, "tn")
    return f'<div class="{cls}">{text}</div>'


def math_html(expr):
    """Render de SymPy a HTML legible (usa unicode, sin MathJax)."""
    return sp.pretty(expr, use_unicode=True).replace("\n", "<br>").replace(" ", "&nbsp;")


# ===================== GRAFICADOR =====================
def plot_fn(f, df=None, tang=None, x0=-5, x1=5):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    xs = np.linspace(x0, x1, 1200)

    def safe(fn):
        ys = []
        for xv in xs:
            try:
                y = fn(float(xv))
                ys.append(y if np.isfinite(y) else np.nan)
            except (ZeroDivisionError, ValueError, TypeError, OverflowError):
                ys.append(np.nan)
        return np.array(ys, dtype=float)

    fy = safe(fnum(f))
    ax.plot(xs, fy, color="#58a6ff", lw=2.2, label="f(x)")
    if df is not None:
        dy = safe(fnum(df))
        ax.plot(xs, dy, color="#3fb950", lw=1.8, ls="--", label="f′(x)")
    if tang is not None:
        a, m, b = tang
        ax.plot(xs, m * xs + b, color="#e3b341", lw=1.8, ls=":", label="tangente")
        ax.plot([a], [m * a + b], "o", color="#e3b341", ms=7)

    # puntos críticos si se piden
    ax.axhline(0, color="#30363d", lw=0.8)
    ax.axvline(0, color="#30363d", lw=0.8)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_facecolor("#0d1117")
    fig.patch.set_facecolor("#161b22")
    ax.tick_params(colors="#8b949e")
    for s in ax.spines.values():
        s.set_color("#30363d")
    ax.set_xlabel("x", color="#8b949e")
    ax.set_ylabel("y", color="#8b949e")
    return fig


# ---- helpers numéricos ----
def safe_vals(fn, xs):
    out = []
    for xv in xs:
        try:
            y = fn(float(xv))
            y = float(np.asarray(y, dtype=float).ravel()[0]) if np.ndim(y) else float(y)
            out.append(y if np.isfinite(y) else np.nan)
        except Exception:
            out.append(np.nan)
    return np.array(out, dtype=float)


def safe_at(fn, xv):
    try:
        y = fn(float(xv))
        y = float(np.asarray(y, dtype=float).ravel()[0]) if np.ndim(y) else float(y)
        return y if np.isfinite(y) else np.nan
    except Exception:
        return np.nan


# ===================== INTERFAZ =====================
st.set_page_config(page_title="CalcDiff — Solucionador de Cálculo Diferencial", page_icon="🧮", layout="wide")

# ---------- DISEÑO MODERNO (sin <style>: estilos inline, a prueba del sanitizador) ----------
# El fondo oscuro global y los acentos de color vienen de .streamlit/config.toml (tema dark).

# ---- Hero con gradiente (100% inline) ----
st.markdown(
    """
    <div style="
        background: linear-gradient(135deg, rgba(88,166,255,.16), rgba(163,113,247,.12) 55%, rgba(63,185,80,.12));
        border: 1px solid #2a3a55; border-radius: 18px; padding: 26px 32px; margin-bottom: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,.45);">
        <h1 style="margin:0; font-size:2.1rem; font-weight:800; letter-spacing:-0.5px; color:#58a6ff;">
            🧮 CalcDiff
            <span style="font-size:1.05rem; font-weight:600; color:#a371f7;">· solucionador paso a paso</span>
        </h1>
        <p style="margin:8px 0 12px; color:#8b949e; font-size:.95rem;">
            Escribe una función, elige el capítulo y observa cómo la terminal <b>teclea la solución</b> — con gráfica incluida.
        </p>
        <span style="display:inline-block; margin-right:6px; padding:4px 14px; border-radius:999px; background:rgba(88,166,255,.12); border:1px solid rgba(88,166,255,.4); color:#58a6ff; font-size:.78rem; font-weight:600;">⚡ SymPy · motor simbólico exacto</span>
        <span style="display:inline-block; padding:4px 14px; border-radius:999px; background:rgba(63,185,80,.12); border:1px solid rgba(63,185,80,.4); color:#3fb950; font-size:.78rem; font-weight:600;">📈 Graficador incluido</span>
    </div>
    """,
    unsafe_allow_html=True,
)

CAPITULOS = {
    "derivada": "1. Derivada por reglas (potencia, suma, producto, cociente, cadena)",
    "cadena": "2. Regla de la cadena en profundidad",
    "tangente": "3. Recta tangente y normal en un punto",
    "criticos": "4. Puntos críticos, máximos y mínimos",
    "analisis": "5. Análisis: crecimiento y concavidad",
    "limite": "6. Límites (sustitución y formas 0/0)",
}
EJEMPLOS = {
    "derivada": ["x**3 - 3*x + 2", "x**2*sin(x)", "(x**2+1)/(x-1)", "exp(x)*cos(x)"],
    "cadena": ["sin(x**2+1)", "ln(cos(x))", "(2*x+1)**5", "sqrt(x**2+4)"],
    "tangente": ["x**2", "x**3-3*x", "sin(x)", "1/x"],
    "criticos": ["x**3-3*x", "x**4-4*x**2", "x**2*exp(-x)", "sin(x)+x"],
    "analisis": ["x**3-3*x", "x**4-2*x**2", "exp(-x**2)", "ln(x)"],
    "limite": ["(x**2-4)/(x-2)", "sin(x)/x", "1/x", "(sqrt(x+1)-1)/x"],
}

with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center; padding:4px 0 14px; border-bottom:1px solid #2a3a55; margin-bottom:12px;">
            <div style="font-size:1.9rem;">🧮</div>
            <div style="font-weight:800; font-size:1.05rem; letter-spacing:.5px; color:#58a6ff;">CalcDiff</div>
            <div style="color:#8b949e; font-size:.72rem;">cálculo diferencial · paso a paso</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**⚙️ Entrada del problema**")
    cap = st.selectbox("Capítulo", list(CAPITULOS.keys()), format_func=lambda k: CAPITULOS[k])
    src = st.text_input("Función f(x)", value="", placeholder="ej: x**3 - 3*x + 2 (también acepta x^3)")
    ejemplo = st.selectbox("…o elige un ejemplo", [""] + EJEMPLOS[cap])
    if ejemplo and src == "":
        src = ejemplo
    a_pt = st.text_input("Punto x = a (tangente / evaluación)", value="1")
    lim_a = st.text_input("Valor al que tiende x (solo límites)", value="2")
    x0 = st.number_input("Ventana x mín", value=-5.0)
    x1 = st.number_input("Ventana x máx", value=5.0)
    speed = st.slider("Velocidad del tecleo (ms/repaint)", 5, 80, 25)
    resolver = st.button("▶ Resolver y mostrar pasos", type="primary", use_container_width=True)

TERM_BOX = st.empty()
col_plot = st.empty()

if resolver:
    if not src.strip():
        st.error("Escribe una función f(x) primero.")
        st.stop()
    lines = [("note", "// Terminal — recibiendo problema…")]
    try:
        f = parse_fn(src)
        lines.append(("title", f"calc> f(x) = {sp.pretty(f, use_unicode=True)}"))
        if cap in ("derivada", "cadena"):
            df, steps = derivative_steps(f)
            lines.append(("note", "Paso 1 — Identifico la estructura de f y aplico reglas:"))
            for i, (r, e) in enumerate(steps, 1):
                lines.append(("note", f"   {i}) {r}"))
            ds = sp.simplify(df)
            lines.append(("title", "Paso 2 — Derivada simplificada:"))
            lines.append(("result", f"✔ f′(x) = {sp.pretty(ds, use_unicode=True)}"))
            type_terminal(lines, speed)
            col_plot.pyplot(plot_fn(f, ds, None, x0, x1))

        elif cap == "tangente":
            a = float(a_pt)
            df = sp.diff(f, x)
            lines.append(("note", f"Paso 1 — Derivo f: f′(x) = {sp.pretty(df, use_unicode=True)}"))
            m = float(df.subs(x, a))
            fa = float(f.subs(x, a))
            lines.append(("note", f"Paso 2 — Evalúo en x = {a}: f({a}) = {fa} (punto de tangencia), m = f′({a}) = {fmt_val(m)}"))
            b = fa - m * a
            lines.append(("title", f"Paso 3 — Ecuación punto–pendiente: y − y₁ = m(x − x₁)"))
            lines.append(("result", f"✔ Tangente: y = {fmt_val(m)}·x + {fmt_val(b)}"))
            if abs(m) > 1e-12:
                lines.append(("result", f"✔ Normal:  y = {fmt_val(-1/m)}·x + {fmt_val(fa + a/m)}"))
            else:
                lines.append(("note", "Tangente vertical: x = " + fmt_val(a)))
            type_terminal(lines, speed)
            col_plot.pyplot(plot_fn(f, df, (a, m, b), x0, x1))

        elif cap in ("criticos", "analisis"):
            df, ddf = full_analysis(f)
            lines.append(("note", f"Paso 1 — f′(x) = {sp.pretty(df, use_unicode=True)}"))
            lines.append(("note", f"Paso 2 — f′′(x) = {sp.pretty(ddf, use_unicode=True)}"))
            # raíces exactas si SymPy puede, numéricas como respaldo
            try:
                crit = sp.solve(sp.Eq(df, 0), x)
                crit = [c for c in crit if c.is_real]
                metodo = "resueltas simbólicamente con SymPy"
            except Exception:
                crit = []
                metodo = "búsqueda numérica"
            if not crit:
                fnum_df = fnum(df)
                xs = np.linspace(x0, x1, 4000)
                ys = safe_vals(fnum_df, xs)
                sgn = np.sign(ys)
                for i in range(len(xs) - 1):
                    if sgn[i] * sgn[i+1] < 0:
                        crit.append(sp.nsolve(df, x, (xs[i] + xs[i+1]) / 2))
                metodo = "búsqueda numérica (nsolve)"
            lines.append(("title", f"Paso 3 — f′(x) = 0 → {metodo}"))
            for c in crit[:10]:
                cv = float(c)
                if x0 - 1e-9 <= cv <= x1 + 1e-9:
                    yv = float(f.subs(x, cv))
                    d2v = float(ddf.subs(x, cv)) if not np.isnan(float(ddf.subs(x, cv))) else 0
                    if d2v < -1e-8:
                        cls = "MÁXIMO local (f′′<0)"
                    elif d2v > 1e-8:
                        cls = "MÍNIMO local (f′′>0)"
                    else:
                        cls = "posible inflexión (f′′≈0)"
                    lines.append(("result", f"✔ x* = {fmt_val(cv)}  →  f(x*) = {fmt_val(yv)}  [{cls}]"))
            if cap == "analisis":
                lines.append(("title", "Paso 4 — Tabla de signos (crecimiento y concavidad):"))
                pts = sorted([float(x0)] + [float(c) for c in crit if x0 <= float(c) <= x1] + [float(x1)])
                fn_df, fn_ddf = fnum(df), fnum(ddf)
                for i in range(len(pts) - 1):
                    mid = (pts[i] + pts[i+1]) / 2
                    s1 = np.sign(safe_at(fn_df, mid))
                    s2 = np.sign(safe_at(fn_ddf, mid))
                    if s1 != 0:
                        lines.append(("note", f"   ({fmt_val(pts[i])}, {fmt_val(pts[i+1])}): f′ {'>' if s1>0 else '<'} 0 → f {'CRECE ↑' if s1>0 else 'DECRECE ↓'}, "
                                                f"f′′ {'>' if s2>0 else '<'} 0 → {'cóncava ∪' if s2>0 else 'cóncava ∩'}"))
            type_terminal(lines, speed)
            col_plot.pyplot(plot_fn(f, df, None, x0, x1))

        elif cap == "limite":
            a = sp.Rational(lim_a) if "/" in lim_a else sp.Float(lim_a)
            lines.append(("note", f"Paso 1 — Sustitución directa x → {a}:"))
            direct = sp.limit(f, x, a, "+-")
            sub = f.subs(x, a)
            if sub.is_finite is not False and not sub.has(sp.zoo, sp.nan):
                lines.append(("result", f"✔ lim f(x) con x→{a} = {sp.pretty(sub, use_unicode=True)} (por sustitución)"))
            else:
                lines.append(("note", f"   f({a}) = {sp.pretty(sub, use_unicode=True)} → forma indeterminada. Aplico álgebra o límites laterales:"))
                li = sp.limit(f, x, a, "-")
                ld = sp.limit(f, x, a, "+")
                lines.append(("note", f"   Por la izquierda: {sp.pretty(li, use_unicode=True)}"))
                lines.append(("note", f"   Por la derecha:  {sp.pretty(ld, use_unicode=True)}"))
                if sp.simplify(li - ld) == 0:
                    lines.append(("result", f"✔ Los límites laterales coinciden: lim f(x) = {sp.pretty(li, use_unicode=True)}"))
                else:
                    lines.append(("err", f"✖ Los límites laterales difieren ({li} ≠ {ld}) → el límite NO existe."))
            type_terminal(lines, speed)
            col_plot.pyplot(plot_fn(f, None, None, x0, x1))

    except Exception as e:
        lines.append(("err", f"✖ Error: {e}"))
        type_terminal(lines, speed)
        with st.expander("Ver traza técnica"):
            st.code(traceback.format_exc())
else:
    terminal_html(
        '<div class="tn">// Terminal — configura el problema en el panel izquierdo '
        'y pulsa «▶ Resolver y mostrar pasos».</div>'
    )
