# coLEX — DeepFish

**Repo:** https://github.com/iuliapetrisor/coLEX · UiPath Future Forward Hackathon 2026, „Agents in Action”

![Prototipul coLEX](docs/screenshot.png)

## Scop

coLEX este un agent care ține sistemele unei firme fintech în pas cu legea. Când apare un act nou, decide dacă privește firma, găsește fiecare loc care trebuie schimbat (contracte, termeni, tarife, proceduri, tichete, cod), propune modificarea și o trimite oamenilor spre aprobare. coLEX propune, omul decide: nu face merge și nu oferă consultanță juridică.

## Problema rezolvată

O companie de servicii financiare primește zeci de mii de documente de reglementare pe an, iar doar o mică parte o privesc. Când unul contează, termenele sunt scurte, iar regula veche stă împrăștiată în cod, configurări și contracte. Codul neconform nu dă eroare: trece testele și rulează liniștit, dar greșit. coLEX automatizează trierea și căutarea, iar oamenii păstrează decizia.

## Cum funcționează

Prototipul urmărește un flux de acte oficiale UE pentru o instituție de plată fictivă din România, PayRo SRL.

1. **Watcher** preia actele noi din flux.
2. **Triage** decide dacă actul privește firma și spune de ce (potrivire cu profilul firmei plus un apel la un model mic). Actele irelevante sunt arhivate cu motiv.
3. **Impact analyst** navighează **Company Map**, o hartă deterministă a firmei construită din șase surse simulate (Confluence, OneDrive, Google Drive, Jira, intranet, repo de cod). Raportează fiecare loc afectat cu dovezi (resursă + linii) și citare (CELEX + articol).
4. **Liaison** trimite fiecare constatare echipei care o deține. Când îi lipsește un fapt, întreabă juridicul.
5. **Coder** creează un branch, scrie patch-ul, rulează testele într-un sandbox și revizuiește dacă pică. Inginerul aprobă; nimic nu e îmbinat automat.
6. **Verifier** și un **audit** cu lanț de hash-uri păstrează urma fiecărui pas: ce a văzut agentul, ce a decis, cine a aprobat.

Garanții: surse de documente doar în citire, agenții nu pot face merge pe `main`, citatul din lege trebuie să existe cuvânt cu cuvânt în liniile citate, IBAN, CNP, e-mail și telefon sunt înlocuite înainte de orice apel la model, testele rulează fără rețea și cu limite, bugete de tokeni și cost per act. Detalii în `SECURITY.md`.

## Rezultate măsurate

O rulare înregistrată pe un sandbox de 21 de resurse și 23 de acte (`docs/RESULTS.md`):

- Triere: 3 din 3 acte relevante găsite, 20 din 20 acte irelevante arhivate
- Locuri afectate: 7 din 9 găsite; 7 din 13 raportate erau așteptate
- Rutare: 7 din 7 către echipa corectă
- 3 cereri de modificare a codului, niciuna îmbinată automat
- Cost: între 0,05 și 0,11 USD per act relevant

Limite asumate: o singură rulare pe date fabricate, iar regulile au fost reglate pe aceleași date. Pe acest sandbox mic, harta nu economisește context. Testul de scalare merge până la 5.021 de resurse (`docs/SCALE.md`).

## Tehnologii

- **Python**, Pydantic, PyYAML
- **Modele** prin OpenRouter (`openai/gpt-4.1-mini`), cu mod offline din răspunsuri înregistrate
- **Runtime**: mașină de stări cu checkpoint după fiecare pas, așteptări umane durabile, reluare după restart, SQLite
- **Console**: FastAPI, Uvicorn, Jinja2 (aprobări, hartă, registre)
- **Slack** (slack_bolt) pentru aprobări, pe aceeași cale de decizie ca în Console
- **Git** în sandbox: branch-uri și patch-uri, fără merge
- **PayRo**: aplicație demo fictivă, cu două „telefoane” (trimițător și destinatar), pentru verificarea beneficiarului (VoP)

## Rulare

```
make setup && make test
make demo OFFLINE=1     # scenariul complet, fără rețea
make console            # Console pe http://127.0.0.1:8000
make payro              # PayRo pe :8001 și :8002
```

PayRo SRL și toate datele din sandbox sunt fictive.
