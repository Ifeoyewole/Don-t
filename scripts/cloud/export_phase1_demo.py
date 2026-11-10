"""Package already-executed GCP results as a static, offline engineering report.

No cloud access, inference, review workflow or model downloads. Provider text is
HTML-escaped. The package contains results, never tokens, keys or model weights.
"""
import argparse
import html
import json
from pathlib import Path
import shutil
import zipfile


def esc(value):
    return html.escape(str(value))


def package(results, output, build_id):
    results, output = Path(results), Path(output)
    if output.exists():
        raise ValueError('Use a new output directory; preserve earlier packages')
    output.mkdir(parents=True)
    summary = json.loads((results/'summary.json').read_text())
    sections = []
    for row in summary['frames']:
        number = row['frame']
        if type(number) is not int:
            raise ValueError('Invalid frame identity')
        name = 'frame-'+str(number)
        source = results/name
        target = output/name
        target.mkdir()
        for file in source.iterdir():
            if file.is_file() and (file.suffix in ('.json', '.jpg', '.png') or file.name == 'original.bin'):
                shutil.copyfile(file, target/file.name)
        report = json.loads((source/'unified-report.json').read_text())
        findings = ''.join('<li>'+esc(f.get('label'))+': '+esc(f.get('explanation', f.get('status')))
                           +'</li>' for f in report['preliminary_findings']) or '<li>No mapped defect finding established.</li>'
        classes = report['components'].get('inspect_view', {}).get('evidence', {}).get('classes', {})
        predictions = ''.join('<tr><td>'+esc(label)+'</td><td>'+esc(value.get('probability'))
                              +'</td><td>'+esc(value.get('status'))+'</td></tr>'
                              for label, value in classes.items())
        masks = ''.join('<figure><img src="'+name+'/'+esc(f.name)+'" alt="Actual binary SAM2 mask"/>'
                        '<figcaption>'+esc(f.name)+'</figcaption></figure>' for f in sorted(target.glob('mask-*.png')))
        geometry = report['joint_measurement']
        values = '; '.join(str(c['value'])+' px ('+str(c['meaning'])+')' for c in geometry['candidates'])
        if not values:
            values = 'joint_geometry_not_reliable — no supported joint-gap candidate'
        analysis = report['gemini'].get('analysis', {})
        disagreements = ''.join('<li>'+esc(s)+'</li>' for s in report['disagreements_and_limits'])
        original = 'original.jpg' if (target/'original.jpg').exists() else 'original.bin'
        sections.append(f'''<section><h2>Frame {number}</h2>
<p class="status">{esc(report['decision'])} · Gemini: {esc(report['gemini']['status'])}</p>
<p>{esc(report['summary'])}</p>
<div class="pair"><figure><img src="{name}/{original}" alt="Original CCTV frame"/><figcaption>Original frame</figcaption></figure>
<figure><img src="{name}/overlay.png" alt="Unified masks and pixel boundary overlay"/><figcaption>Unified annotated result</figcaption></figure></div>
<h3>Preliminary findings</h3><ul>{findings}</ul>
<h3>Joint boundary evidence</h3><p>{esc(values)}</p>
<p>Physical millimetres: unavailable. Calibration: {esc(geometry['calibration_status'])}.
Projected mask-band width and visible ring spacing are not verified axial joint gap.</p>
<h3>Actual SAM2 masks</h3><div class="masks">{masks}</div>
<h3>Inspect View evidence</h3><table><thead><tr><th>Class</th><th>Model probability</th><th>Validation status</th></tr></thead><tbody>{predictions}</tbody></table>
<p>ISWDS proposals retain source numeric IDs where their class mapping is unavailable; they do not establish new defect support.</p>
<h3>Gemini interpretation</h3><p>{esc(analysis.get('summary', 'Unavailable'))}</p>
<h3>Disagreements and limitations</h3><ul>{disagreements}</ul>
<p>Recorded inference timings: {esc(json.dumps(report['latency_seconds']))}</p>
<p>Source SHA-256: <code>{esc(report['image_sha256'])}</code></p>
<p><a href="{name}/unified-report.json">Complete unified JSON, model evidence and authenticated Gemini receipts</a></p></section>''')
    document = '''<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/><title>JointInspect Phase 1 demonstration</title>
<style>*{box-sizing:border-box}body{font:16px/1.55 system-ui,sans-serif;background:#eef3fa;color:#17243a;margin:0}
main{max-width:1200px;margin:auto;padding:24px;overflow-wrap:anywhere}h1,h2,h3{color:#074aaa}.banner,.status{background:#fff0c8;padding:12px;border-radius:8px}
section{background:white;padding:24px;margin:24px 0;border-radius:12px;overflow-wrap:anywhere}
.pair,.masks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:18px}
.masks{grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr))}figure{margin:0;min-width:0}img{width:100%;height:auto;object-fit:contain}
table{width:100%;border-collapse:collapse;table-layout:fixed}td,th{text-align:left;border-bottom:1px solid #dce4f0;padding:8px;overflow-wrap:anywhere}
code{overflow-wrap:anywhere}a{color:#0754c8}@media(max-width:600px){main,section{padding:12px}}</style></head><body><main>
<h1>JointInspect · Phase 1 unified inspection</h1><p class="banner">Development prototype — REVIEW_REQUIRED. No engineering acceptance,
verified physical measurements or measured defect-recognition improvement is claimed.</p>'''
    document += '<p>GCP Cloud Build: '+esc(build_id)+'. Outcome: '+esc(summary['status'])+'.</p>'
    document += '<p>Inspect View r5 + one ISWDS specialist + SAM2.1 + OpenCV + Vertex Gemini. All model inference executed in GCP.</p>'
    document += ''.join(sections)+'</main></body></html>'
    (output/'index.html').write_text(document)
    shutil.copyfile(results/'summary.json', output/'summary.json')
    (output/'README.txt').write_text('Open index.html in a browser. Static real-run evidence, not an adjudication interface.\n'
                                   'Review original images, masks and uncertainty before interpreting pixel boundary candidates.\n'
                                   'No commercial permission, engineering acceptance or accuracy claim is granted by this package.\n')
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for file in output.rglob('*'):
            if file.is_file():
                z.write(file, file.relative_to(output))
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--build-id', required=True)
    args = parser.parse_args()
    print(package(args.results, args.output, args.build_id))
