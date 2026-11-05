import hashlib
from pathlib import Path
import re
import shutil
import subprocess


INLINE_MATH = {
    "[-1,1] x [-1,1]": r"[-1,1]\times[-1,1]",
    "x^2 + y^2 <= 1": r"x^2+y^2\leq 1",
    "pi/4": r"\pi/4",
    "sqrt(pi * (4 - pi) / N)": r"\sqrt{\pi(4-\pi)/N}",
    "1/sqrt(N)": r"N^{-1/2}",
    "Sigma_t": r"\Sigma_t",
    "Sigma_t = 1 per cm": r"\Sigma_t=1\,\mathrm{cm}^{-1}",
    "Sigma_t * dx": r"\Sigma_t\,\mathrm{d}x",
    "U": r"U",
    "[0,1)": r"[0,1)",
    "SD(T0_hat) = sqrt(p * (1-p) / N)": r"\operatorname{SD}(\widehat T_0)=\sqrt{p(1-p)/N}",
    "exp(-1)": r"e^{-1}",
    "exp(-1) = 0.36787944": r"e^{-1}\simeq0.36787944",
    "T0(L) = exp(-Sigma_t L)": r"T_0(L)=e^{-\Sigma_t L}",
    "T0": r"T_0",
    "T": r"T",
    "T + R + A": r"T+R+A",
    "Y_i": r"Y_i",
    "u_i": r"u_i",
    "sqrt(sum(u_i^2)) / r": r"\sqrt{\sum_{i=1}^{r}u_i^2}/r",
    "r = 3": r"r=3",
    "n": r"n",
    "mean": r"\overline Y",
    "sum_sq": r"S_2",
    "sqrt((sum_sq/n - mean^2)/(n-1))": r"\sqrt{\bigl(S_2/n-\overline Y^{\,2}\bigr)/(n-1)}",
    "phi0(x) = exp(-Sigma_t x)": r"\phi_0(x)=e^{-\Sigma_t x}",
    "Sigma_a * integral(phi dx)": r"\Sigma_a\int_0^L\phi(x)\,\mathrm{d}x",
    "phi_c(x) = integral(psi_c(x, mu) dmu, -1, 1)": r"\phi_c(x)=\int_{-1}^{1}\psi_c(x,\mu)\,\mathrm{d}\mu",
    "phi = phi0 + phi_c": r"\phi=\phi_0+\phi_c",
}

DISPLAY_MATH = {
    "pi_hat = 4 * n_inside / N\nVar(pi_hat) = pi * (4 - pi) / N\nSD(pi_hat) = sqrt(pi * (4 - pi) / N)": r"""\begin{align}
\widehat\pi &= 4\frac{N_{\mathrm{inside}}}{N},\\
\operatorname{Var}(\widehat\pi) &= \frac{\pi(4-\pi)}{N},\\
\operatorname{SD}(\widehat\pi) &= \sqrt{\frac{\pi(4-\pi)}{N}}.
\end{align}""",
    "dT0/dx = -Sigma_t * T0,  T0(0) = 1\nT0(x) = exp(-Sigma_t * x)\nfree_path = -log(1 - U) / Sigma_t": r"""\begin{align}
\frac{\mathrm{d}T_0}{\mathrm{d}x} &=-\Sigma_tT_0,
& T_0(0)&=1,\\
T_0(x)&=e^{-\Sigma_t x},\\
\ell&=-\frac{\ln(1-U)}{\Sigma_t}.
\end{align}""",
    "mu * d(psi_c)/dx + Sigma_t * psi_c = q(x)\nq(x) = (Sigma_s/2) * [phi0(x) + phi_c(x)]": r"""\begin{align}
\mu\frac{\partial\psi_c}{\partial x}+\Sigma_t\psi_c &= q(x),\\
q(x)&=\frac{\Sigma_s}{2}\bigl[\phi_0(x)+\phi_c(x)\bigr].
\end{align}""",
    "a = exp(-tau),  b = (1-a)/tau,  tau = Sigma_t*dx/abs(mu)\npsi_out = a*psi_in + (q/Sigma_t)*(1-a)\npsi_average = b*psi_in + (q/Sigma_t)*(1-b)": r"""\begin{align}
a&=e^{-\tau},&
b&=\frac{1-a}{\tau},&
\tau&=\frac{\Sigma_t\Delta x}{|\mu|},\\
\psi_{\mathrm{out}}&=a\psi_{\mathrm{in}}+
  \frac{q}{\Sigma_t}(1-a),\\
\overline\psi&=b\psi_{\mathrm{in}}+
  \frac{q}{\Sigma_t}(1-b).
\end{align}""",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def escape_tex(value):
    replacements = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
        "$": r"\$", "&": r"\&", "#": r"\#", "%": r"\%",
        "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def plain(value):
    result = re.sub(r"\b([0-9]+(?:\.[0-9]+)?)e([+-]?[0-9]+)\b", lambda match: r"\(" + match.group(1) + r"\times10^{" + str(int(match.group(2))) + r"}\)", escape_tex(value))
    return re.sub(r"\bpi\b", lambda match: r"\(\pi\)", result)


def inline(value, citations=True):
    pattern = r"\x60([^\x60]+)\x60|\*\*(.+?)\*\*|\[([^\]]+)\]\((https?://[^)]+)\)|\[(\d+(?:,\s*\d+)*)\]"
    pieces = []
    previous = 0
    for match in re.finditer(pattern, value):
        pieces.append(plain(value[previous:match.start()]))
        code, bold, label, url, references = match.groups()
        if code is not None:
            formula = INLINE_MATH.get(code)
            pieces.append(r"\(" + formula + r"\)" if formula else r"\path{" + code + "}")
        elif bold is not None:
            pieces.append(r"\textbf{" + inline(bold, citations=False) + "}")
        elif url is not None:
            pieces.append(r"\href{" + url.replace("%", r"\%") + "}{" + plain(label) + "}")
        elif citations:
            pieces.append(r"\cite{" + ",".join("ref" + number.strip() for number in references.split(",")) + "}")
        else:
            pieces.append(escape_tex(match.group(0)))
        previous = match.end()
    pieces.append(plain(value[previous:]))
    return "".join(pieces)


def paragraph(lines, index):
    content = [lines[index].strip()]
    index += 1
    while index < len(lines) and lines[index].strip() and not lines[index].startswith(("#", "|", "![", chr(96) * 3, "<!--")):
        content.append(lines[index].strip())
        index += 1
    return " ".join(content), index


def table_cell(value):
    uncertainty = re.fullmatch(r"([0-9.]+) \+/- ([0-9.]+)", value)
    if uncertainty:
        return r"\shortstack[r]{" + uncertainty.group(1) + r"\\\(\pm\)" + uncertainty.group(2) + "}"
    return inline(value).replace("+/-", r"\(\pm\)")


def write_latex(markdown, source_folder, project_folder, title, stage_label):
    project_folder.mkdir(parents=True, exist_ok=True)
    images = project_folder / "images"
    images.mkdir(exist_ok=True)
    lines = markdown.splitlines()
    index = 0
    body = []
    image_hashes = {}
    bibliography = False
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line == "<!-- pagebreak -->":
            body.append(r"\clearpage")
            index += 1
            continue
        if line.startswith("# "):
            body.append(r"\begin{center}{\LARGE\bfseries " + inline(line[2:]) + r"}\end{center}")
            index += 1
            continue
        if line.startswith("## "):
            heading = line[3:]
            if heading == "References":
                body.append(r"\begin{thebibliography}{9}")
                bibliography = True
            else:
                if bibliography:
                    body.append(r"\end{thebibliography}")
                    bibliography = False
                body.append(r"\section*{" + inline(heading) + "}")
            index += 1
            continue
        if line.startswith(chr(96) * 3):
            index += 1
            code = []
            while index < len(lines) and not lines[index].startswith(chr(96) * 3):
                code.append(lines[index])
                index += 1
            block = "\n".join(code).strip()
            if block not in DISPLAY_MATH:
                raise ValueError("A report equation needs a LaTeX definition: " + block)
            body.append(DISPLAY_MATH[block])
            index += 1
            continue
        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if image_match:
            image_path = (source_folder / image_match.group(2)).resolve()
            image_target = images / image_path.name
            shutil.copyfile(image_path, image_target)
            image_hashes["images/" + image_path.name] = digest(image_target)
            height = {
                "pi_estimate.png": 195, "convergence.png": 235, "runtime.png": 210,
                "uncollided_transmission.png": 195, "residuals.png": 190,
                "transmission_comparison.png": 245, "reference_residuals.png": 210,
                "particle_fates.png": 200,
            }.get(image_path.name, 210)
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            caption = image_match.group(1)
            if index < len(lines) and re.match(r"\*\*Figure \d+\.\*\*", lines[index]):
                caption, index = paragraph(lines, index)
                caption = re.sub(r"^\*\*Figure \d+\.\*\*\s*", "", caption)
            body.append(
                r"\begin{figure}[H]\centering" + "\n"
                + r"\includegraphics[width=\linewidth,height=" + str(height) + r"pt,keepaspectratio]{images/" + image_path.name + "}\n"
                + r"\caption{" + inline(caption).replace("+/-", r"\(\pm\)") + "}\n" + r"\end{figure}"
            )
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                values = [value.strip() for value in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", value) for value in values):
                    rows.append(values)
                index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            caption = None
            if index < len(lines) and re.match(r"\*\*Table \d+\.\*\*", lines[index]):
                caption, index = paragraph(lines, index)
                caption = re.sub(r"^\*\*Table \d+\.\*\*\s*", "", caption)
            alignment = "l" + "r" * (len(rows[0]) - 1)
            table = [r"\begin{table}[H]\centering\small" if caption else r"\begin{center}\small", r"\setlength{\tabcolsep}{5pt}", r"\renewcommand{\arraystretch}{1.22}", r"\begin{tabular}{@{}" + alignment + r"@{}}", r"\toprule"]
            table.append(" & ".join(table_cell(value) for value in rows[0]) + r"\\")
            table.append(r"\midrule")
            table.extend(" & ".join(table_cell(value) for value in row) + r"\\" for row in rows[1:])
            table.extend([r"\bottomrule", r"\end{tabular}"])
            if caption:
                table.extend([r"\caption{" + inline(caption) + "}", r"\end{table}"])
            else:
                table.append(r"\end{center}")
            body.append("\n".join(table))
            continue
        value, index = paragraph(lines, index)
        if bibliography:
            entry = re.match(r"\[(\d+)\]\s*(.*)", value)
            if not entry:
                raise ValueError("Reference entry has no number")
            body.append(r"\bibitem{ref" + entry.group(1) + "}" + inline(entry.group(2), citations=False))
        else:
            body.append(inline(value).replace("+/-", r"\(\pm\)") + "\n")
    if bibliography:
        body.append(r"\end{thebibliography}")
    preamble = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=0.72in,headheight=14pt,headsep=13pt]{geometry}
\usepackage{amsmath,amssymb,graphicx,booktabs,array,caption,float,xcolor}
\usepackage{microtype,titlesec,fancyhdr,xurl}
\definecolor{reportblue}{HTML}{176B87}
\usepackage[colorlinks=true,allcolors=reportblue]{hyperref}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\captionsetup{font=small,labelfont=bf,skip=5pt}
\titleformat{\section}{\large\bfseries\color{reportblue}}{}{0pt}{}
\titlespacing*{\section}{0pt}{9pt}{5pt}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small @@STAGE@@}
\fancyhead[R]{\small Research report | November 2026}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\setlength{\emergencystretch}{1.5em}
\hypersetup{pdftitle={@@TITLE@@},pdfauthor={Auhornish Adel}}
\begin{document}
"""
    preamble = preamble.replace("@@STAGE@@", escape_tex(stage_label)).replace("@@TITLE@@", escape_tex(title))
    main = project_folder / "main.tex"
    main.write_text(preamble + "\n\n".join(body) + "\n\\end{document}\n", encoding="utf-8", newline="\n")
    return {"main": str(main), "main_sha256": digest(main), "images_sha256": image_hashes}


def compile_pdf(project_folder, pdf_path, compiler=None):
    executable = compiler or shutil.which("tectonic") or shutil.which("pdflatex")
    if not executable:
        raise RuntimeError("Install Tectonic or a TeX distribution, or use --source-only and compile report/latex/main.tex in Overleaf.")
    executable = str(Path(executable).resolve())
    build = project_folder / "build"
    build.mkdir(exist_ok=True)
    main = (project_folder / "main.tex").resolve()
    if Path(executable).stem.lower() == "tectonic":
        command = [executable, "--keep-logs", "--outdir", str(build.resolve()), str(main)]
        passes = 1
    else:
        command = [executable, "-interaction=nonstopmode", "-halt-on-error", "-output-directory=" + str(build.resolve()), str(main)]
        passes = 2
    with (build / "compiler-output.txt").open("w", encoding="utf-8") as stream:
        for repetition in range(passes):
            subprocess.run(command, cwd=project_folder, stdout=stream, stderr=subprocess.STDOUT, check=True)
    generated = build / "main.pdf"
    if not generated.exists():
        raise RuntimeError("LaTeX did not produce a PDF. Check report/latex/build/compiler-output.txt.")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(generated, pdf_path)
    return {"pdf_sha256": digest(pdf_path), "compiler": Path(executable).name}
