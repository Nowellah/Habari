"""Keyword rules for harm categories below the danger fast path.

All patterns run on text produced by danger.normalize (lowercase, no
apostrophes). The lexicon is English only: messages in other languages are
handled by the unmatched-message policy in triage.py.
"""
import re
from dataclasses import dataclass

from .schemas import Category, Severity


@dataclass(frozen=True)
class LexiconRule:
    rule_id: str
    category: Category
    severity: Severity
    patterns: tuple[re.Pattern, ...]
    weak: bool = False

    def matches(self, text: str) -> bool:
        return any(p.search(text) for p in self.patterns)


def _rule(rule_id, category, severity, patterns, weak=False) -> LexiconRule:
    return LexiconRule(rule_id, category, severity, tuple(re.compile(p) for p in patterns), weak)


LEXICON_RULES: tuple[LexiconRule, ...] = (
    _rule("abuse_sexual_or_physical", Category.ABUSE, Severity.S3, (
        r"\btouch(es|ed|ing)? (me|my (body|private|breasts?|chest|thighs?))\b",
        r"\bprivate parts\b",
        r"\brap(e|ed|es|ing)\b",
        r"\bdefile\w*",
        r"\bmolest\w*",
        r"\bsexual(ly)? (abus|assault|harass)\w*",
        r"\b(beat|beats|beating|beaten|hit|hits|hitting|slap\w*|burn\w*|whip\w*|cane[sd]?|caning) me\b",
        r"\b(forc\w+|made|makes|make) me\b.{0,25}\b(sex|sleep with|undress|strip|naked)\b",
        r"\bsleep(ing)? with (me|him|her)\b",
    )),
    _rule("sextortion_threat", Category.SEXTORTION, Severity.S3, (
        r"\bsextort\w*",
        r"\b(threat\w*|blackmail\w*|black mail)\b",
        r"\b(will|going to|gonna|wants? to|said (he|she|they) will)\b.{0,20}\b(leak|post|share|expose|publish|show)\b",
        r"\b(leak|post|share|publish|expose|show|send)\b.{0,40}\b(my|the|those)\b.{0,15}\b(nudes?|naked|photos?|pictures?|pics?|videos?|images?)\b",
        r"\bor (else )?(he|she|they)\b.{0,20}\b(post|share|leak|send|show)\b",
        # v0.3: a condition on the child ("if I don't / if I stop ...") tied to their images
        r"\bif i (dont|do not|wont|will not|stop|refuse|block)\b.{0,60}\b(nudes?|naked|photos?|pictures?|pics?|videos?)\b",
    )),
    # v0.3: an adult asking for images or for the child to undress is grooming at S3, not S2.
    _rule("grooming_image_request", Category.GROOMING, Severity.S3, (
        r"\b(ask|asks|asking|asked|wants?|begging|begs|beg|pressur\w*)\b (me )?(for|to (send|take))\b.{0,20}\b(nudes?|naked|pics?|pictures?|photos?|videos?|selfies?)\b",
        r"\b(take|took|taking|takes) off (my|your) (clothes|shirt|dress|top|skirt|uniform|trousers)\b",
        r"\b(our|this|the) (chats?|talks?|messages?|friendship|relationship) (is|are) (special|secret|just between us)\b",
        r"\b(dont|do not|must not|mustnt|never) tell (your|my) (parents|mum|mom|dad|mother|father|family)\b.{0,20}\b(about )?(us|me|our|this|we)\b",
        r"\b(parents|mum|mom|dad|mother|father|family) (would|will|wouldnt|wont) (not )?understand\b.{0,20}\b(us|our|this|we)\b",
        r"\b(wants?|asked|asking|asks|told|tells?|invit\w*) (me )?to (come|go) to (his|her|their) (place|house|home|room|hotel|flat|apartment)\b",
    )),
    # v0.3: sexual or doctored images of the child being shared by peers.
    _rule("image_based_abuse", Category.HARASSMENT, Severity.S3, (
        r"\b(edit\w*|photoshop\w*|put|morph\w*|stuck) my (face|head|photo|picture)\b.{0,20}\b(on|onto|into)\b",
        r"\b(fake|edited|dirty|naked|nude|sexy) (picture|photo|pic|video|image)s? of me\b",
        r"\b(picture|photo|pic|video|image)s? of me (naked|undressed|in the (toilet|bathroom|shower))\b",
    )),
    _rule("grooming_request_for_images", Category.GROOMING, Severity.S2, (
        r"\b(asked|asking|wants?|told|tells?) me to send\b.{0,30}\b(photos?|pictures?|pics?|nudes?|videos?)\b",
        r"\bsend (him|her|them) (a )?(nudes?|naked|pics? of my body)\b",
        r"\b(our|a) secret\b",
        r"\bdont tell (anyone|anybody|your parents|my parents)\b",
        r"\b(older|grown|adult) (man|woman|guy|person|friend)\b",
        r"\basked (me )?(how old|my age)\b",
    )),
    _rule("grooming_meetup", Category.GROOMING, Severity.S3, (
        r"\b(wants?|asked|asking|told|tells?) (me )?to meet\b",
        r"\bmeet (him|her|them) (alone|secretly)\b",
    )),
    _rule("harassment_online", Category.HARASSMENT, Severity.S2, (
        r"\bbull(y|ied|ies|ying)\b",
        r"\binsult\w*",
        r"\bmock(ed|ing|s)?\b",
        r"\blaugh(ing|ed)? at me\b",
        r"\bhumiliat\w*",
        r"\bfake (account|profile)\b",
        r"\babusive (messages?|comments?|words)\b",
        r"\b(stalk|harass)\w*",
        r"\bname calling\b",
        r"\bcall(s|ed|ing)? me names\b",
        r"\b(mak(e|es|ing)|made) fun of\b",
        r"\btease\w*|\bteasing\b",
        r"\bspread(ing)? rumou?rs\b",
        r"\bkeeps? (messaging|texting|calling) me\b",
    )),
    _rule("account_scam", Category.ACCOUNT_SCAM, Severity.S2, (
        r"\bscam\w*",
        r"\bfraud\w*",
        r"\bhack(ed|er|ing)?\b",
        r"\bphishing\b",
        r"\bstole(n)? my (account|password|phone|money)\b",
        r"\bpassword\b",
        r"\blost (my )?money\b",
        r"\bimpersonat\w*",
        r"\bwon a prize\b",
        r"\b(double|triple) (my|your) (money|savings)\b",
        r"\bsend (them|him|her) (all )?my (savings|money|pocket money)\b",
    )),
    _rule("exposure_harmful_content", Category.EXPOSURE, Severity.S1, (
        r"\bporn\w*",
        r"\bsexual (video|content|pictures?|images?)\b",
        r"\bviolent (video|content)\b",
        r"\bgore\b",
        r"\bdisturbing\b",
        r"\binappropriate (video|content|pictures?|images?)\b",
        r"\b(video|clip|picture|photo)s? of (someone|somebody|people|a (person|man|woman|child|boy|girl))\b.{0,15}\b(getting|being) (hurt|killed|beaten|stabbed|shot|cut)\b",
        r"\b(cant|can not|cannot) stop (seeing|thinking about) (it|that video|the video|those pictures)\b",
        r"\bkeep seeing it\b",
    )),
    _rule("distress_or_help_request", Category.OTHER, Severity.S2, (
        r"\bhelp me\b",
        r"\bplease help\b",
        r"\bneed help\b",
        r"^help$",
        r"\b(scared|afraid|unsafe|terrified)\b",
    ), weak=True),
)

GREETING = re.compile(r"^(hi+|hello+|hey+|habari|oli otya|good (morning|afternoon|evening))\W*$")

IMAGE_TERMS = re.compile(r"\b(nudes?|naked|photos?|pictures?|pics?|videos?|images?|screenshots?)\b")
PAYMENT_TERMS = re.compile(
    r"\b(money|pay|paid|paying|payment|airtime|momo|mobile money|ugx|shillings?|cash|bitcoin)\b|\$\s?\d+"
)
DEMAND_TERMS = re.compile(
    r"\b(asked|asking|wants?|demand\w*|forc\w+|telling me|told me|said|says|threat\w*|or else|unless)\b"
    r"|\bif i (dont|do not|wont|will not|refuse)\b"
)

TRUSTED_ROLES_FROM_CONTEXT = frozenset({"family", "teacher", "guardian"})
TRUSTED_ROLE_TEXT = re.compile(
    r"\bmy (step ?)?(father|dad|daddy|mother|mom|mum|mummy|parents?|guardian|caretaker|uncle|aunt|auntie)\b"
    r"|\bmy step(dad|father|mum|mom|mother)\b"
    r"|\b(my|our|the) (class |head |games |form |football |sports )?(teacher|headmaster|headmistress|headteacher|matron|principal|coach|warden|patron)\b"
    r"|\b(my|our|the) (pastor|priest|imam|sheikh|catechist)\b"
)
HARM_WORDS = re.compile(
    r"\b(touch\w*|beat\w*|hit|hits|slap\w*|abus\w*|threat\w*|hurt\w*|forc\w+|scared|afraid|naked|nude|"
    r"photos?|pictures?|videos?|undress\w*|sex\w*|kiss\w*|rap(e|ed|ing)|caned?|punish\w*|starv\w*)\b"
)

HINT_SEVERITY = {
    "self_harm": Severity.S4,
    "immediate_danger": Severity.S4,
    "abuse": Severity.S3,
    "sextortion": Severity.S3,
    "grooming": Severity.S2,
    "harassment": Severity.S2,
    "account_scam": Severity.S2,
    "exposure": Severity.S1,
}

CATEGORY_PRIORITY = (
    Category.SELF_HARM,
    Category.IMMEDIATE_DANGER,
    Category.ABUSE,
    Category.SEXTORTION,
    Category.GROOMING,
    Category.HARASSMENT,
    Category.ACCOUNT_SCAM,
    Category.EXPOSURE,
    Category.OTHER,
)
