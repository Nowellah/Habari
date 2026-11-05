"""Synthetic evaluation set. No real child data, ever.

Run:  python eval/scripts/make_synthetic.py   (writes eval/data/synthetic.csv)

Each template is written once and filled with a few slot values. The test split
is chosen by TEMPLATE, so the test set never contains a reworded copy of a
training message. Luganda (lg) and Swahili (sw) templates are DRAFTS that need a
native speaker's review before the per-language numbers mean much.

Labels follow the harm table (plan §4.4): self_harm and imminent threats 4;
sextortion with money and a threat 4; sextortion, grooming, authority 3;
bullying, impersonation, scams, gambling 2; upsetting content 1.
"""
import csv
import itertools
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "synthetic.csv"
SEED = 2026

SLOTS = {
    "name": ["a man", "someone", "a boy from my class", "a stranger"],
    "app": ["Instagram", "TikTok", "WhatsApp", "Snapchat"],
    "amount": ["50,000 shillings", "airtime", "20k"],
}
EN_PREFIXES = ["", "please help, ", "I am scared. ", "hi "]

# (template_id, category, severity, role, language, text)
TEMPLATES = [
    # self-harm
    ("en-s1", "self_harm", 4, "", "en", "I want to die, nobody cares about me"),
    ("en-s2", "self_harm", 4, "", "en", "I keep thinking I should kill myself"),
    ("en-s3", "self_harm", 4, "", "en", "I want to hurt myself after what {name} posted on {app}"),
    ("en-s4", "self_harm", 4, "", "en", "there is no reason to live anymore"),
    # threats (imminent danger)
    ("en-t1", "threats", 4, "", "en", "{name} says he is coming to my house tonight"),
    ("en-t2", "threats", 4, "", "en", "{name} on {app} wants to meet me after school and says I must come alone"),
    ("en-t3", "threats", 4, "", "en", "he said he is going to kill me if I tell anyone"),
    ("en-t4", "threats", 4, "", "en", "{name} locked me in the room and took my phone"),
    # sextortion
    ("en-x1", "sextortion", 4, "", "en", "{name} on {app} says I will post your nude pictures unless you send {amount}"),
    ("en-x2", "sextortion", 3, "", "en", "someone wants me to send nude pictures on {app}"),
    ("en-x3", "sextortion", 4, "", "en", "{name} has my private pictures and says send money or else"),
    ("en-x4", "sextortion", 3, "", "en", "he keeps asking me to send naked pictures"),
    # grooming
    ("en-g1", "grooming", 3, "", "en", "an older man on {app} keeps saying I am mature and that we should keep it our secret"),
    ("en-g2", "grooming", 3, "", "en", "{name} sends me airtime and asks me not to tell my parents about our chats"),
    ("en-g3", "grooming", 3, "", "en", "a grown up on {app} buys me gifts and asks for private pictures"),
    # an adult in charge
    ("en-a1", "exposure_by_authority", 3, "authority", "en", "my teacher sends me messages at night on {app}"),
    ("en-a2", "exposure_by_authority", 3, "authority", "en", "my uncle touches me and says I must not tell"),
    ("en-a3", "exposure_by_authority", 3, "authority", "en", "the headteacher asked me to send him a photo of myself"),
    ("en-a4", "exposure_by_authority", 3, "authority", "en", "my father hits me when he sees me on the phone"),
    # bullying
    ("en-b1", "cyberbullying", 2, "", "en", "people in my class keep calling me names on {app}"),
    ("en-b2", "cyberbullying", 2, "", "en", "{name} made a group on {app} just to laugh at me"),
    ("en-b3", "cyberbullying", 2, "", "en", "they say I am ugly and post comments about me every day"),
    ("en-b4", "cyberbullying", 3, "", "en", "{name} wrote kill yourself under my photo"),
    # impersonation
    ("en-i1", "impersonation", 2, "", "en", "someone made a fake {app} account with my name and photos"),
    ("en-i2", "impersonation", 2, "", "en", "{name} is pretending to be me on {app}"),
    ("en-i3", "impersonation", 2, "", "en", "a fake account is sending messages to my friends as me"),
    # scams
    ("en-c1", "scam", 2, "", "en", "someone on {app} said I won a prize and must send money first"),
    ("en-c2", "scam", 2, "", "en", "a man asked me to send mobile money to get a job"),
    ("en-c3", "scam", 2, "", "en", "they asked for my PIN so they can give me free data"),
    # gambling
    ("en-gb1", "gambling_or_betting", 2, "", "en", "my friend made me try betting and I lost my school fees"),
    ("en-gb2", "gambling_or_betting", 2, "", "en", "I keep betting on football on my phone and cannot stop"),
    ("en-gb3", "gambling_or_betting", 2, "", "en", "a casino app keeps sending me offers"),
    # upsetting content
    ("en-n1", "inappropriate_content", 1, "", "en", "I saw a video with fighting and blood on {app}"),
    ("en-n2", "inappropriate_content", 1, "", "en", "someone sent me a sexual video I did not want to see"),
    ("en-n3", "inappropriate_content", 1, "", "en", "I saw scary pictures on {app} and now I cannot sleep"),
    # Luganda (DRAFT, needs native review)
    ("lg-s1", "self_harm", 4, "", "lg", "Njagala okufa, tewali anfaako"),
    ("lg-s2", "self_harm", 4, "", "lg", "nja kwetta olw'ebyo bye bampandiikira ku {app}"),
    ("lg-x1", "sextortion", 3, "", "lg", "Omuntu ansaba ssente nga tasindika bifaananyi byange"),
    ("lg-x2", "sextortion", 3, "", "lg", "omusajja ku {app} ayagala ebifaananyi ebyobwereere"),
    ("lg-t1", "threats", 4, "", "lg", "omusajja anninda ku ssomero era agamba nti ajja kunzita"),
    ("lg-a1", "exposure_by_authority", 3, "authority", "lg", "omusomesa wange ampandiikira ekiro ku {app}"),
    ("lg-a2", "exposure_by_authority", 3, "authority", "lg", "kojja wange ankwatako era agamba nti sigamba muntu"),
    ("lg-b1", "cyberbullying", 2, "", "lg", "abaana mu kibiina bampita amannya ku {app}"),
    ("lg-gb1", "gambling_or_betting", 2, "", "lg", "mukwano gwange yandaga okubeetinga ne mfiirwa ssente"),
    ("lg-c1", "scam", 2, "", "lg", "omuntu ku {app} ansaba ssente angeme ekirabo"),
    # Swahili (DRAFT, needs native review)
    ("sw-s1", "self_harm", 4, "", "sw", "nataka kufa, hakuna anayenijali"),
    ("sw-x1", "sextortion", 3, "", "sw", "mtu ananiomba pesa na picha zangu za uchi"),
    ("sw-a1", "exposure_by_authority", 3, "authority", "sw", "mwalimu wangu ananitumia ujumbe usiku"),
    ("sw-gb1", "gambling_or_betting", 2, "", "sw", "rafiki yangu alinifundisha kubeti nikapoteza pesa"),
    ("sw-b1", "cyberbullying", 2, "", "sw", "watoto darasani wananitukana kwenye {app}"),
]


def _test_templates():
    """Per category and language, the last template goes to test (at least one per category)."""
    last = {}
    for tid, cat, _, _, lang, _ in TEMPLATES:
        last[(cat, lang)] = tid
    return set(last.values())


def _fills(text, rng):
    keys = [k for k in SLOTS if "{" + k + "}" in text]
    if not keys:
        return [text]
    combos = list(itertools.product(*(SLOTS[k] for k in keys)))
    rng.shuffle(combos)
    return [text.format(**dict(zip(keys, c))) for c in combos[:2]]


def generate():
    rng = random.Random(SEED)
    test_ids = _test_templates()
    rows = []
    for tid, cat, sev, role, lang, text in TEMPLATES:
        prefixes = EN_PREFIXES if lang == "en" else ["", "bambi "] if lang == "lg" else ["", "tafadhali "]
        for body in _fills(text, rng):
            for prefix in prefixes:
                rows.append({"template_id": tid, "text": prefix + body, "category": cat, "severity": sev,
                             "role": role, "language": lang, "split": "test" if tid in test_ids else "train"})
    return rows


def write(path=OUT):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = generate()
    with path.open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path, len(rows)


if __name__ == "__main__":
    p, n = write()
    print(f"wrote {n} rows to {p}")
