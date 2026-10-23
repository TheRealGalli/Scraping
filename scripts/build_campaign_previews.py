"""Build review-only email concepts; does not connect to the sending worker."""

from pathlib import Path
import html
import json
import shutil
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "templates" / "campaigns"
ASSETS = OUT / "assets"
SOURCE = Path("/Users/carlogalli/Desktop/CSD Station/csd.station.italia/public/sito-social")

CAMPAIGNS = [
    dict(id="consulenza", name="Consulenza AI", tag="MENO LAVORO RIPETITIVO", title="Meno copia-incolla.<br>Più tempo per te.", subject="Un’idea per alleggerire il lavoro ripetitivo", preheader="Partiamo da un’attività concreta, non da un altro software.", image="consulenza.jpg", source="ig-1.jpg", alt="Otto fra documenti e un grande tasto copia e incolla, dal carosello CSD Station", body="Fogli da aggiornare, documenti da cercare, informazioni da ricopiare. Ti aiuto a capire dove l’AI e le automazioni possono semplificare il lavoro della tua attività.", note="Si parte da un processo concreto. Si sceglie insieme cosa migliorare.", cta="Scopri la consulenza", path="/", message="Ciao Carlo! Vorrei capire come semplificare un’attività ripetitiva con la consulenza AI."),
    dict(id="training", name="Training AI", tag="IMPARARE FACENDO", title="L’AI al lavoro.<br>Con un metodo.", subject="Un training AI costruito sul lavoro del tuo team", preheader="Esercizi concreti, strumenti e verifica delle risposte.", image="training.jpg", source="ig-4.jpg", alt="Otto accanto a un punto interrogativo, dal carosello sul training AI", body="Aprire una chat è facile. Usarla bene richiede pratica. Nei miei training lavoriamo su esempi vicini al tuo team: richieste più chiare, risultati da verificare e attenzione ai dati.", note="Il programma si costruisce sulle attività e sugli obiettivi del team.", cta="Scopri il training", path="/training-ai/", message="Ciao Carlo! Mi interessa un training AI per il mio team. Possiamo parlarne?"),
    dict(id="nfc", name="Card NFC", tag="UN TAP. LA TUA SCHEDA.", title="La tua scheda Google.<br>A portata di tap.", subject="Card, plate o stand: un tap per aprire la tua scheda Google", preheader="NFC e QR code per rendere più semplice il percorso verso le recensioni.", image="nfc.jpg", source="car-1.jpg", alt="Otto presenta card, plate adesiva e stand NFC CSD Station", body="Quando un cliente vuole lasciare una recensione, rendigli semplice il primo passo. Con card, plate e stand NFC, un tap o il QR code aprono la tua scheda Google.", note="Tre formati. Configurazione concordata insieme. Nessuna promessa sulle stelle.", cta="Guarda i tre formati", path="/card-nfc/", message="Ciao Carlo! Vorrei informazioni sui formati NFC per la mia attività."),
    dict(id="sito", name="Sito web", tag="LA TUA VETRINA ONLINE", title="Ti cercano.<br>Fatti trovare bene.", subject="Un sito chiaro per chi cerca la tua attività", preheader="Servizi, informazioni e contatto: tutto al posto giusto.", image="sito.jpg", source=None, alt="Otto presenta un sito web su computer e smartphone", body="Chi arriva sul tuo sito dovrebbe capire subito cosa fai e come contattarti. Realizzo siti chiari, curati e pensati per lo smartphone, con un percorso semplice verso una richiesta.", note="Contenuti, stile e funzioni si definiscono nel preventivo.", cta="Scopri i siti", path="/sito-social/#siti", message="Ciao Carlo! Vorrei informazioni per il sito della mia attività."),
    dict(id="social", name="Social", tag="LA TUA ATTIVITÀ, RACCONTATA BENE", title="Tu fai il tuo lavoro.<br>I contenuti li preparo io.", subject="Caroselli e reel da approvare e pubblicare", preheader="Un piano condiviso, contenuti curati e approvazione semplice.", image="social.jpg", source=None, alt="Otto organizza una serie di contenuti social nei colori avorio e lime", body="Caroselli, reel e contenuti per raccontare quello che fai. Pianifichiamo insieme, preparo i materiali e tu li approvi prima di pubblicarli. Anche partendo dai video che hai già.", note="Quantità, formati e calendario si concordano prima di iniziare.", cta="Scopri i contenuti social", path="/sito-social/#social", message="Ciao Carlo! Vorrei capire come organizzare i contenuti social della mia attività."),
    dict(id="media", name="Slide e video", tag="DA UN’IDEA A QUALCOSA DA MOSTRARE", title="Le tue idee.<br>Una forma che si capisce.", subject="Slide e video per spiegare meglio quello che fai", preheader="Presentazioni, animazioni e montaggio a partire dai tuoi materiali.", image="media.jpg", source=None, alt="Otto lavora con slide, un ciak e un simbolo di riproduzione video", body="Una proposta da presentare, un servizio da spiegare, un video da montare. Trasformo testi, dati e materiali in slide chiare e video curati, con uno stile coerente con la tua attività.", note="Un progetto alla volta, dal materiale iniziale alla consegna.", cta="Guarda slide e video", path="/video-slide/", message="Ciao Carlo! Vorrei informazioni per realizzare slide o video per la mia attività."),
]


def email(c):
    esc = html.escape
    return f'''<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>CSD Station · {esc(c['name'])}</title>
<style>body{{margin:0;padding:0}}table{{border-collapse:collapse}}a{{color:#20251c}}img{{border:0;outline:none}}@media(max-width:620px){{.shell{{width:100%!important}}.pad{{padding-left:24px!important;padding-right:24px!important}}.headline{{font-size:36px!important;letter-spacing:-1.7px!important}}.stack{{display:block!important;width:100%!important;box-sizing:border-box!important}}.art{{width:240px!important;max-width:100%!important;margin:0 auto!important}}.copy{{padding:26px 0 0!important}}.outer{{padding:0!important}}}}</style></head>
<body style="margin:0;background:#edece6;color:#181b15;font-family:Arial,Helvetica,sans-serif;">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{esc(c['preheader'])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td class="outer" align="center" style="padding:28px 12px;">
<table role="presentation" class="shell" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;background:#fffef9;">
<tr><td class="pad" style="padding:26px 36px 23px;border-bottom:1px solid #e7e8df;"><table role="presentation" width="100%"><tr><td style="font-size:20px;font-weight:700;letter-spacing:-1px;">CSD Station<span style="color:#71952a;">.</span></td><td align="right" style="font-size:10px;font-weight:700;letter-spacing:.4px;color:#4f5a43;">{esc(c['name']).upper()}</td></tr></table></td></tr>
<tr><td class="pad" style="padding:32px 36px 0;"><span style="display:inline-block;background:#d4fa82;padding:6px 10px;font-size:9px;line-height:14px;letter-spacing:1px;font-weight:700;border-radius:20px;">{esc(c['tag'])}</span>
<h1 class="headline" style="margin:19px 0 25px;font-size:43px;line-height:1.04;letter-spacing:-2.1px;font-weight:800;color:#11150e;">{c['title']}</h1></td></tr>
<tr><td class="pad" style="padding:0 36px 28px;"><table role="presentation" width="100%"><tr>
<td class="stack" width="230" valign="top"><img class="art" src="assets/{c['image']}" alt="{esc(c['alt'])}" width="230" style="display:block;width:230px;max-width:100%;height:auto;border-radius:12px;"></td>
<td class="stack copy" width="298" valign="middle" style="padding:0 0 0 25px;"><p style="margin:0 0 12px;font-size:14px;line-height:1.6;font-weight:700;">Ciao, sono Carlo.</p><p style="margin:0;font-size:14px;line-height:1.7;color:#424a3b;">{esc(c['body'])}</p></td>
</tr></table></td></tr>
<tr><td class="pad" style="padding:0 36px 28px;"><p style="margin:0;padding:15px 0 0;border-top:1px solid #e4e8d9;font-size:12px;line-height:1.65;color:#657056;">{esc(c['note'])}</p></td></tr>
<tr><td class="pad" style="padding:0 36px 29px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td bgcolor="#c5f476" style="background:#c5f476;border-radius:7px;text-align:center;mso-padding-alt:15px 23px;"><a href="https://csd-station.it{c['path']}" target="_blank" style="display:inline-block;padding:15px 23px;font-size:14px;line-height:20px;font-weight:700;color:#17210b;text-decoration:none;">{esc(c['cta'])} &nbsp;↗</a></td></tr></table><p style="margin:16px 0 0;font-size:12px;line-height:1.6;color:#657056;">Preferisci parlarne? <a href="https://wa.me/393518628203?text={quote(c['message'])}" style="color:#354b1b;text-decoration:underline;">Scrivimi su WhatsApp</a>.</p></td></tr>
<tr><td class="pad" style="padding:22px 36px 25px;background:#f1f3e9;border-top:1px solid #e4e8d9;"><p style="margin:0 0 11px;font-size:12px;line-height:1.5;color:#26301e;"><strong>Carlo Galli</strong> · CSD Station<br><a href="mailto:carlo@csd-station.it" style="text-decoration:none;color:#526044;">carlo@csd-station.it</a></p>
<p style="margin:0 0 11px;font-size:10px;line-height:1.6;color:#68715f;">P.IVA 01630510525 · Via Francesco Campana 45<br>53034 Colle di Val d’Elsa (SI), Italia</p>
<p style="margin:0;font-size:10px;line-height:1.7;color:#68715f;">Per non ricevere altre proposte, rispondi <strong>CANCELLAMI</strong>.<br><a href="https://csd-station.it/privacy-policy/" style="color:#526044;text-decoration:underline;">Informativa privacy</a></p></td></tr>
</table></td></tr></table></body></html>'''


def build():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for c in CAMPAIGNS:
        if c["source"]:
            shutil.copyfile(SOURCE / c["source"], ASSETS / c["image"])
        (OUT / f"{c['id']}.html").write_text(email(c), encoding="utf-8")
        body = c['title'].replace('<br>', ' ') + '\n\nCiao, sono Carlo.\n\n' + c['body'] + '\n\n' + c['note']
        body += f"\n\n{c['cta']}: https://csd-station.it{c['path']}\nWhatsApp: https://wa.me/393518628203?text={quote(c['message'])}\n\nCarlo Galli · CSD Station\ncarlo@csd-station.it\nP.IVA 01630510525\nVia Francesco Campana 45, 53034 Colle di Val d’Elsa (SI), Italia\n\nPer non ricevere altre proposte, rispondi CANCELLAMI.\nPrivacy: https://csd-station.it/privacy-policy/\n"
        (OUT / f"{c['id']}.txt").write_text(body, encoding="utf-8")
    manifest = [{k: v for k, v in c.items() if k not in ('source', 'body', 'note', 'title', 'message')} for c in CAMPAIGNS]
    (OUT / 'campaigns.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    build()
