"""Static analytical figures with explicit units and scope."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Polygon, Patch
from shapely.geometry import shape
import numpy as np

plt.rcParams.update({'font.family': ['Malgun Gothic', 'DejaVu Sans'],
                     'axes.unicode_minus': False, 'figure.dpi': 150,
                     'axes.spines.top': False, 'axes.spines.right': False})


def save(fig, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor='white')
    plt.close(fig)


def bars(labels, values, title, unit, note, path, horizontal=False):
    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.subplots_adjust(left=.27 if horizontal else .12, bottom=.25, top=.85, right=.94)
    positions = np.arange(len(labels))
    if horizontal:
        ax.barh(positions, values, color='#216a81')
        ax.set_yticks(positions, labels)
        ax.invert_yaxis()
        ax.set_xlabel(unit)
        ax.grid(axis='x', alpha=.18)
    else:
        ax.bar(positions, values, color='#216a81', width=.6)
        ax.set_xticks(positions, labels)
        ax.set_ylabel(unit)
        ax.grid(axis='y', alpha=.18)
    ax.set_axisbelow(True)
    ax.ticklabel_format(axis='x' if horizontal else 'y', style='plain')
    fig.suptitle(title, x=.06, ha='left', fontsize=16, fontweight='bold')
    fig.text(.06, .07, note, ha='left', va='bottom', fontsize=9, linespacing=1.5)
    save(fig, path)


def choropleth(features, field, title, note, path):
    values = [f['properties'].get(field) for f in features]
    known = [v for v in values if v is not None and np.isfinite(v)]
    if not known:
        raise ValueError('Map has no observed values')
    fig, ax = plt.subplots(figsize=(10, 9))
    fig.subplots_adjust(left=.04, right=.91, bottom=.18, top=.88)
    norm = colors.Normalize(0, max(known))
    cmap = plt.get_cmap('YlGnBu')
    for feature, value in zip(features, values):
        geom = shape(feature['geometry'])
        polygons = list(geom.geoms) if geom.geom_type == 'MultiPolygon' else [geom]
        color = '#d5d5d5' if value is None else cmap(norm(value))
        for poly in polygons:
            ax.add_patch(Polygon(np.asarray(poly.exterior.coords), facecolor=color,
                                 edgecolor='white', linewidth=.3))
            for ring in poly.interiors:
                ax.add_patch(Polygon(np.asarray(ring.coords), facecolor='white', edgecolor='none'))
    ax.autoscale_view()
    ax.set_aspect(1 / np.cos(np.deg2rad(37.55)))
    ax.set_axis_off()
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=.65, fraction=.035)
    cb.set_label('9월 추정 이동량 합계 (통행)')
    ax.legend(handles=[Patch(facecolor='#d5d5d5', label='경계/코드 연결 불확실 (unknown)')],
              loc='lower left', frameon=False, fontsize=9)
    fig.suptitle(title, x=.06, ha='left', fontsize=16, fontweight='bold')
    fig.text(.06, .035, note, fontsize=9, linespacing=1.5)
    save(fig, path)
