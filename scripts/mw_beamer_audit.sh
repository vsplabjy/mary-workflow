#!/usr/bin/env bash
# Adapted from Heaticy/vsp-beamer @ e7bf4e5e5588ee10a386e6c79668e50f9b749124.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 PDF [PDF ...]" >&2
  exit 2
fi

for command in mutool pdfinfo pdftoppm identify jq awk; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing PDF audit dependency: $command" >&2
    exit 2
  fi
done

tmp_root=$(mktemp -d)
trap 'rm -rf "$tmp_root"' EXIT
failed=0

for pdf in "$@"; do
  if [[ ! -f "$pdf" ]]; then
    echo "Missing PDF: $pdf" >&2
    failed=1
    continue
  fi

  name=$(basename "${pdf%.pdf}")
  work="$tmp_root/$name-$RANDOM"
  mkdir -p "$work/raster"

  mutool draw -q -F stext.json -o "$work/text.json" "$pdf"
  mutool draw -q -F trace -o "$work/trace.xml" "$pdf"

  jq -r '
    .pages | to_entries[] as $page
    | $page.value.blocks[]?
    | select(.type == "text" and .bbox.w > 0 and .bbox.h > 0)
    | [($page.key + 1), .bbox.x, .bbox.y,
       (.bbox.x + .bbox.w), (.bbox.y + .bbox.h)]
    | @tsv
  ' "$work/text.json" > "$work/text.tsv"

  awk '
    /<page mediabox=/ {
      page++
      line = $0
      sub(/^.*mediabox="/, "", line); sub(/".*$/, "", line)
      split(line, box, " ")
      printf "%d\t%.6f\t%.6f\t%.6f\t%.6f\n", page, box[1], box[2], box[3], box[4] > pages
    }
    /<fill_image / {
      line = $0
      sub(/^.*transform="/, "", line); sub(/".*$/, "", line)
      split(line, m, " ")
      x1=m[5]; y1=m[6]
      x2=m[1]+m[5]; y2=m[2]+m[6]
      x3=m[3]+m[5]; y3=m[4]+m[6]
      x4=m[1]+m[3]+m[5]; y4=m[2]+m[4]+m[6]
      xmin=xmax=x1; ymin=ymax=y1
      if (x2<xmin) xmin=x2; if (x2>xmax) xmax=x2
      if (x3<xmin) xmin=x3; if (x3>xmax) xmax=x3
      if (x4<xmin) xmin=x4; if (x4>xmax) xmax=x4
      if (y2<ymin) ymin=y2; if (y2>ymax) ymax=y2
      if (y3<ymin) ymin=y3; if (y3>ymax) ymax=y3
      if (y4<ymin) ymin=y4; if (y4>ymax) ymax=y4
      printf "%d\t%.6f\t%.6f\t%.6f\t%.6f\n", page, xmin, ymin, xmax, ymax > images
    }
  ' pages="$work/pages.tsv" images="$work/images.tsv" "$work/trace.xml"
  touch "$work/images.tsv"

  awk -v pdf="$pdf" '
    BEGIN { tolerance=6; bad=0 }
    NR==FNR { x0[$1]=$2; y0[$1]=$3; x1[$1]=$4; y1[$1]=$5; next }
    {
      p=$1
      if ($2 < x0[p]-tolerance || $3 < y0[p]-tolerance ||
          $4 > x1[p]+tolerance || $5 > y1[p]+tolerance) {
        printf "%s: page %d text bbox outside page: [%.2f %.2f %.2f %.2f]\n", pdf, p, $2, $3, $4, $5 > "/dev/stderr"
        bad=1
      }
    }
    END { exit bad }
  ' "$work/pages.tsv" "$work/text.tsv" || failed=1

  awk -v pdf="$pdf" '
    BEGIN { tolerance=1; bad=0 }
    NR==FNR { x0[$1]=$2; y0[$1]=$3; x1[$1]=$4; y1[$1]=$5; next }
    {
      p=$1
      if ($2 < x0[p]-tolerance || $3 < y0[p]-tolerance ||
          $4 > x1[p]+tolerance || $5 > y1[p]+tolerance) {
        printf "%s: page %d image bbox outside page: [%.2f %.2f %.2f %.2f]\n", pdf, p, $2, $3, $4, $5 > "/dev/stderr"
        bad=1
      }
    }
    END { exit bad }
  ' "$work/pages.tsv" "$work/images.tsv" || failed=1

  awk -v pdf="$pdf" '
    function min(a,b) { return a<b?a:b }
    function max(a,b) { return a>b?a:b }
    function area(xa,ya,xb,yb) { return max(0,xb-xa)*max(0,yb-ya) }
    FILENAME==ARGV[1] { pw[$1]=$4-$2; ph[$1]=$5-$3; next }
    FILENAME==ARGV[2] {
      n++; tp[n]=$1; tx0[n]=$2; ty0[n]=$3; tx1[n]=$4; ty1[n]=$5
      next
    }
    {
      p=$1; ia=area($2,$3,$4,$5)
      if (ia > pw[p]*ph[p]*0.70) next
      for (i=1; i<=n; i++) {
        if (tp[i]!=p || ty0[i]<38 || ty1[i]>ph[p]-20) continue
        ta=area(tx0[i],ty0[i],tx1[i],ty1[i])
        overlap=area(max(tx0[i],$2),max(ty0[i],$3),min(tx1[i],$4),min(ty1[i],$5))
        if (ta>0 && overlap/ta>0.65) {
          printf "%s: page %d image covers %.0f%% of a body text block\n", pdf, p, 100*overlap/ta > "/dev/stderr"
          bad=1
        }
      }
    }
    END { exit bad }
  ' "$work/pages.tsv" "$work/text.tsv" "$work/images.tsv" || failed=1

  awk -v pdf="$pdf" '
    function min(a,b) { return a<b?a:b }
    function max(a,b) { return a>b?a:b }
    function area(xa,ya,xb,yb) { return max(0,xb-xa)*max(0,yb-ya) }
    NR==FNR { ph[$1]=$5-$3; next }
    {
      p=$1
      if ($3>=38 && $5<=ph[p]-20) {
        for (i=1; i<=n; i++) if (pp[i]==p) {
          a=area($2,$3,$4,$5); b=area(xx0[i],yy0[i],xx1[i],yy1[i])
          overlap_width=max(0,min($4,xx1[i])-max($2,xx0[i]))
          overlap_height=max(0,min($5,yy1[i])-max($3,yy0[i]))
          min_width=min($4-$2,xx1[i]-xx0[i])
          min_height=min($5-$3,yy1[i]-yy0[i])
          top_delta=$3-yy0[i]
          if (top_delta<0) top_delta=-top_delta
          if (min_width>80 && min_height>8 &&
              top_delta/min_height<0.45 &&
              overlap_width/min_width>0.80 && overlap_height/min_height>0.80) {
            printf "%s: page %d body text blocks substantially overlap\n", pdf, p > "/dev/stderr"
            bad=1
          }
        }
        n++; pp[n]=p; xx0[n]=$2; yy0[n]=$3; xx1[n]=$4; yy1[n]=$5
      }
    }
    END { exit bad }
  ' "$work/pages.tsv" "$work/text.tsv" || failed=1

  pdftoppm -q -r 24 -gray -png "$pdf" "$work/raster/page"
  page=0
  for image in "$work"/raster/page-*.png; do
    page=$((page + 1))
    ink=$(identify -quiet -format '%[fx:1-mean]' "$image")
    if awk -v ink="$ink" 'BEGIN { exit !(ink < 0.0005) }'; then
      echo "$pdf: page $page appears blank (ink ratio $ink)" >&2
      failed=1
    fi
  done

  echo "[audit] $pdf"
done

if [[ $failed -ne 0 ]]; then
  echo "PDF visual audit failed." >&2
  exit 1
fi

echo "PDF visual audit passed."
