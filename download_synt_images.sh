#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but not installed." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$SCRIPT_DIR/synt-images"
MANIFEST_PATH="$TARGET_DIR/manifest.tsv"

mkdir -p "$TARGET_DIR"

printf 'filename\tlicense\tattribution\tsource_page\tsource_image\n' > "$MANIFEST_PATH"

download() {
  local url="$1"
  local filename="$2"
  local license="$3"
  local page="$4"
  local attribution="$5"

  curl -L --fail --retry 3 --retry-delay 2 --retry-all-errors \
    --output "$TARGET_DIR/$filename" \
    "$url"

  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$filename" \
    "$license" \
    "$attribution" \
    "$page" \
    "$url" \
    >> "$MANIFEST_PATH"
}

download \
  "https://upload.wikimedia.org/wikipedia/commons/5/58/Art-broken-explosion-glass_%2824300206666%29.jpg" \
  "broken-glass-explosion.jpg" \
  "CC0" \
  "https://commons.wikimedia.org/wiki/File:Art-broken-explosion-glass_(24300206666).jpg" \
  "none"
download \
  "https://upload.wikimedia.org/wikipedia/commons/7/7c/Broken_glass_on_the_road.JPG" \
  "broken-glass-road.jpg" \
  "CC0" \
  "https://commons.wikimedia.org/wiki/File:Broken_glass_on_the_road.JPG" \
  "none"
download \
  "https://upload.wikimedia.org/wikipedia/commons/3/3b/Shattered_light_fixture_3.jpg" \
  "broken-glass-light-fixture.jpg" \
  "CC0" \
  "https://commons.wikimedia.org/wiki/File:Shattered_light_fixture_3.jpg" \
  "none"

download \
  "https://upload.wikimedia.org/wikipedia/commons/d/da/Smoke_of_incenses_Sri_Dalada_Maligawa.jpg" \
  "smoke-incense-sri-dalada.jpg" \
  "CC0" \
  "https://commons.wikimedia.org/wiki/File:Smoke_of_incenses_Sri_Dalada_Maligawa.jpg" \
  "none"
download \
  "https://upload.wikimedia.org/wikipedia/commons/b/b2/Incense_in_India.jpg" \
  "smoke-incense-india.jpg" \
  "CC0" \
  "https://commons.wikimedia.org/wiki/File:Incense_in_India.jpg" \
  "none"
download \
  "https://upload.wikimedia.org/wikipedia/commons/f/f3/Smoke_Photography_5.jpg" \
  "smoke-photography-5.jpg" \
  "CC BY 2.0" \
  "https://commons.wikimedia.org/wiki/File:Smoke_Photography_5.jpg" \
  "attribution required"

download \
  "https://upload.wikimedia.org/wikipedia/commons/7/73/Fire-damaged_building_in_Kotlas_%2801%29.jpg" \
  "fire-damage-kotlas-01.jpg" \
  "CC0" \
  "https://commons.wikimedia.org/wiki/File:Fire-damaged_building_in_Kotlas_(01).jpg" \
  "none"
download \
  "https://upload.wikimedia.org/wikipedia/commons/e/e3/National_Photo_Co._front_room_after_fire_LCCN2016826393.jpg" \
  "fire-damage-national-photo-co.jpg" \
  "Public Domain" \
  "https://commons.wikimedia.org/wiki/File:National_Photo_Co._front_room_after_fire_LCCN2016826393.jpg" \
  "none"
download \
  "https://upload.wikimedia.org/wikipedia/commons/e/ed/After_the_fire_10.jpg" \
  "fire-damage-after-the-fire-10.jpg" \
  "CC BY-SA 4.0" \
  "https://commons.wikimedia.org/wiki/File:After_the_fire_10.jpg" \
  "attribution + share-alike required"

echo "Downloaded images to $TARGET_DIR"
echo "Wrote license manifest to $MANIFEST_PATH"
