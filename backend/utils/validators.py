"""Input validation and recursive text cleanup helpers."""

import re
from typing import List, Optional

import httpx
from pydantic import BaseModel, validator

from config import settings

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_CONTROL_CHARACTERS = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPECIAL_PASSWORD_CHARACTER = re.compile(r'[!@#$%^&*(),.?":{}|<>]')
_DISPOSABLE_CACHE = {}

PERSONAL_EMAIL_DOMAINS = frozenset(
    """
126.com 139.com 163.com 1800banks.com 189.cn 2925.com 3fdn.com 93re.com a2qp.com abybuy.com adeany.com
advitise.com affekopf.ch ailicke.com aituvip.com aixne.com aixnv.com akdip.com alisaol.com aliyun.com
allrealfinanz.com almatips.com alosp.com alreval.com alysz.com amazon-center.shop american-tall.com
amozix.com amzreports.online anarac.com anidaw.com aniross.com anypsd.com aol.com apostv.com aprte.com
arcadein.com arktico.com artbycookie.com aubady.com auxille.com avtolev.com awsl.uk ayfoto.com azqas.com
balawo.com barneu.com bettereve.com bhamweekly.com binech.com boftm.com boixi.com bountyptylimited.info
boxnavi.com byagu.com cafesui.com caftee.com ceberium.com cengrop.com cevipsa.com chacuo.net chonxi.com
ckqtlcsvqw.shop claudd.com claudecollection.shop cnanb.com cnieux.com cohdi.com coinxt.net
comfortapotheek.com cosxo.com cpav3.com crowfiles.shop cutsup.com cxwet.com daddygo.site daikoa.com
dbkmail.de dboso.com delorex.com desiys.com devbike.com dhnow.com dietna.com dnsclick.com docsign.site
dotzq.com doulas.org dreamercast.shop dretnar.com dropcourse.net dropmeon.com duclongshop.com dvdpit.com
e-bazar.org e052.com ecstor.com educart.shop effexts.com eiveg.com elafans.com elerso.com encode-inc.com
enmaila.com eosada.com eosatx.com eoslux.com ermael.com estebanmx.com euucn.com eveist.com exmab.com
exuge.com eynlong.com fabtivia.com fastmail.com faxico.com fdigimail.web.id feanzier.com featcore.com
feroxid.com fingso.com finloe.com fkainc.com flyrine.com fouraprilone.online foxmail.com fp-sys.com
freans.com fuddydaddy.com funteka.com fxtubes.com ghostmailz.xyz gmail.com gmx.com gmx.net godfare.com
gonaute.com googlemail.com govfederal.ca h2beta.com haja.me handrik.com hanhanmeow.top hatuhavote.icu
hdala.com heixs.com hisila.com hkirsan.com horsesontour.com hotmail.be hotmail.com hotrod.top hpari.com
hsfm.co.uk hunterscafe.com icloud.com iconmal.com idawah.com ideuse.com ifoxdd.com ikewe.com imalias.com
imnart.com inmail7.com inphuocthuy.vn inshuan.com internacionalmex.com intobx.com introex.com ioea.net
iphonaticos.com.br iphonatics.shop iswire.com itaolo.com itcess.com ixhale.com japnc.com jetsay.com
jincer.com jmvoice.com jokerstash.cc jqmails.com juhxs.com kaedar.com kenfern.com keokeg.com kerotu.com
kidaroa.com klav6.com kodpan.com lashyd.com lawicon.com lerany.com lero3.com liaphoto.com lifezg.com
linkrer.com linlshe.com live.com lizery.com lsaar.com luvethe.org lwide.com lyunsa.com m.e-v.cc mac.com
macosten.com magos.dev mail-data.net mail.com mail.nuox.eu.org mail.ru mailfm.net mailsd.net mailvq.net
mailvs.net makemoney15.com makemybiz.com maltabitcoinmining.com markoai.my.id mastermind911.com maxric.com
maylx.com me.com megacode.to menitao.com mexvat.com mitrajagoan.store miwacle.com mocvn.com mofpay.com
msarra.com msn.com mustaer.com mxvia.com naprb.com natiret.com ncsar.com nespj.com netfxd.com netinta.com
ngem.net nhatu.com nicloo.com noihse.com notipr.com novatiz.com nsvpn.com nuclene.com numenor.cc oazv.net
obeamb.com octbit.com ofirit.com okhko.com onepvp.com onionred.com onoranzefunebridegiovine.com ontasa.com
onymi.com ordite.com oremal.com ostinmail.com outlook.com outlookua.online ovbest.com oxbridgecertified.info
oxtenda.com parclan.com pekoi.com phamay.com pox2.com professorpk.com prohade.com protectsmail.net proton.me
protonmail.com purfait.com qmailv.com qq.com racaho.com rambara.com ramcen.com ramizan.com rbesar.info
reagantextile.com reeee.online rekaer.com renno.email revoadastore.shop rezato.com rhconseiltn.com
rickix.com roalx.com rosebird.org roudar.com roweryo.com royalvx.com rwstatus.com saierw.com
salave-transportes.com sanzv.com savests.com scatinc.com sdlat.com shaicn.com sheinup.com sicmg.com
siiii.mywire.org sina.cn sina.com sixze.com smail.pw sohu.com spamgourmet.com spotale.com steimports.shop
steveix.com stoptheyap.com student.io.vn sunstones.biz supenc.com svmail.publicvm.com sweemri.com
synarca.com syncax.com sztaoz.com taimb.com taugr.com tdekeg.online techtary.com temp.meshari.dev
tempmail.j78.org tensico.com tenvil.com tgvis.com thenodish.org thesunand.com tirillo.com toolve.com
torridy.com toymarques.shop travile.com trynta.com tunelux.com tutanota.com uaxpress.com udo8.com unite5.com
vcois.com veb37.com venaten.com vip.sina.com viv2.com vlemi.com vxsolar.com waivey.com webofip.com
weekfly.com wifwise.com wikizs.com winocs.com wwc8.com wyla13.com xadoll.com xidealx.com xlcool.com
xmage.live xmailtm.com xredb.com yahoo.cn yahoo.co.jp yahoo.co.uk yahoo.com yakelu.com yandex.com yandex.ru
yeah.net ymhis.com yopmail.com youtvbe.live yusolar.com zarhq.com zealian.com zetiv.store zizo7.com zoho.com
zosce.com
    """.split()
)


class MessageGuard(BaseModel):
    role: str
    content: str

    @validator("role")
    def validate_role(cls, value):
        if value not in {"user", "system", "assistant"}:
            raise ValueError("role must be one of: user, system, assistant")
        return value

    @validator("content")
    def validate_content(cls, value):
        if not value or not value.strip():
            raise ValueError("content cannot be empty")
        if len(value) > 1_000_000:
            raise ValueError("content too long (max 1000000 characters)")
        return value.strip()


def validate_api_key(api_key: str) -> bool:
    return bool(api_key and api_key.startswith("sk-xxai-") and 20 <= len(api_key) <= 128)


def validate_email(email: str) -> bool:
    return bool(email and _EMAIL_PATTERN.match(email))


def _domain(email: str) -> str:
    return email.lower().rsplit("@", 1)[-1] if email and "@" in email else ""


def is_personal_email(email: str) -> bool:
    domain = _domain(email)
    return not domain or domain in PERSONAL_EMAIL_DOMAINS


def check_disposable_email_via_api(domain: str) -> Optional[bool]:
    api_key = getattr(settings, "verifymail_api_key", None)
    if not api_key:
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"https://verifymail.io/api/tester@{domain}", params={"key": api_key}
            )
            response.raise_for_status()
            return response.json().get("block", False)
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def is_disposable_email(email: str) -> bool:
    domain = _domain(email)
    if not domain or domain in PERSONAL_EMAIL_DOMAINS:
        return True
    if domain not in _DISPOSABLE_CACHE:
        result = check_disposable_email_via_api(domain)
        _DISPOSABLE_CACHE[domain] = False if result is None else result
    return _DISPOSABLE_CACHE[domain]


def validate_enterprise_email(email: str) -> dict:
    if not validate_email(email):
        return {"is_valid": False, "error": "Invalid email format"}
    if is_personal_email(email):
        return {
            "is_valid": False,
            "error": "Personal email addresses are not allowed. Please use your enterprise email.",
        }
    if is_disposable_email(email):
        return {
            "is_valid": False,
            "error": (
                "Disposable email addresses are not allowed. "
                f"The domain '{_domain(email)}' has been identified as a disposable email provider."
            ),
        }
    return {"is_valid": True, "error": None}


def sanitize_input(text: str) -> str:
    return re.sub(r"""[<>"']""", "", text or "")[:10000].strip()


def clean_null_characters(text: str) -> str:
    return _CONTROL_CHARACTERS.sub("", text.replace("\x00", "")) if text else text


def clean_detection_data(data):
    if isinstance(data, dict):
        return {key: clean_detection_data(value) for key, value in data.items()}
    if isinstance(data, list):
        return [clean_detection_data(value) for value in data]
    return clean_null_characters(data) if isinstance(data, str) else data


def extract_keywords(text: str) -> List[str]:
    return [word for word in re.findall(r"\w+", text.lower()) if len(word) > 2]


def validate_password_strength(password: str) -> dict:
    checks = (
        (len(password) >= 8, "Password must be at least 8 characters long"),
        (bool(re.search(r"[A-Z]", password)), "Password must contain at least one uppercase letter"),
        (bool(re.search(r"[a-z]", password)), "Password must contain at least one lowercase letter"),
        (bool(re.search(r"\d", password)), "Password must contain at least one number"),
    )
    errors = [message for passed, message in checks if not passed]
    score = sum(25 for passed, _ in checks if passed)
    if _SPECIAL_PASSWORD_CHARACTER.search(password):
        score = min(100, score + 10)
    if len(password) >= 12:
        score = min(100, score + 10)
    return {"is_valid": not errors, "errors": errors, "strength_score": score}


def is_password_strong(password: str) -> bool:
    return validate_password_strength(password)["is_valid"]
