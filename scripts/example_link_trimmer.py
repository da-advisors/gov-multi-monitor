# Bulk trimming down of JSON of links from each page, to get a more manageable list of links
#  and desriptions of pages to monitor as "linked lists" within the overall tracker.
#  Prioritization decisions:
#    1. Emphasize, but not necessarily limit to, actual data sources, especially data *files*.
#    2. PDFs and supporting/explanatory information also important.
#    3. Duplicate links are not needed; just pick one version with the most useful description.
#    4. Within page navigation links (with a `#`) are not needed.
#    5. Ignore links to social media accounts

import json

with open("069_national_health_and_nutrition_examination_survey.json") as f:
    input_json = json.load(f)

social_media_exclusion_list = (
    "https://www.snapchat.com",
    "https://www.twitter.com",
    "https://twitter.com",
    "https://www.x.com" "https://x.com",
    "https://www.facebook.com",
    "https://www.instagram.com",
    "https://www.linkedin.com",
    "https://www.youtube.com",
    "https://www.pinterest.com",
)

out_links = {}

for link in input_json["links"]:
    # Exclusion criteria we won't keep in the list at all
    if link["url"].startswith(social_media_exclusion_list):
        continue
    if "#" in link["url"]:  # Omit within-page navigation tags
        continue
    if link["text"] == "Home":
        continue

    if link["url"] in out_links.keys():
        if link["text"] not in out_links[link["url"]]:
            out_links[link["url"]].append(link["text"])
    else:
        out_links[link["url"]] = [link["text"]]

out_links

# Stitch to YAML
## This YAML will still need to be manually inspected for duplicate descriptions:
## When the same link has appeared with different text on the page, that will here be added
##  as separate lines with the `name: ` key, which is not valid YAML. (Hence why this is manually
##  written as text instead of using a YAML library.)
## This also doesn't yet handle other kinds of text parsing and formatting issues, such as accent/punctuation
##  encoding or strings that themselves include a colon/dash/other YAML reserved character

out_yaml = "linked_urls:\n"
for x in out_links:
    out_yaml += f"  - url: {x}\n"
    for name in out_links[x]:
        out_yaml += f"    name: {name}\n"

out_yaml

with open("069_national_health_and_nutrition_examination_survey.yaml", "w") as file:
    file.write(out_yaml)
