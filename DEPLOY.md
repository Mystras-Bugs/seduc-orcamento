# Deploy no Render — passo a passo

O Render publica apps Python a partir de um repositório Git (GitHub).
Os arquivos de configuração já estão prontos neste projeto:

- `render.yaml`  → Blueprint (cria o serviço automaticamente)
- `Procfile` / `.python-version` → reforço de configuração
- `.gitignore`   → o que não vai para o repositório

> ⚠️ **Plano grátis:** o servidor "dorme" após ~15 min sem uso (o primeiro
> acesso depois disso demora ~30 s para acordar) e o disco é temporário —
> a cada reinício o banco volta ao estado que foi **enviado no commit**.
> Como `data/orcamento.db` está versionado, o site sempre sobe com os dados
> atuais. Novas importações feitas no ar valem até o próximo reinício.
> Para dados permanentes e sem "soneca", use um plano pago com **Disk**.

---

## 1. Pré-requisitos (uma vez)
- Conta no GitHub: <https://github.com>
- Conta no Render: <https://render.com> (pode entrar com o GitHub)
- Git instalado (já usamos aqui).

## 2. Criar o repositório no GitHub
1. Em <https://github.com/new>, crie um repositório (ex.: `seduc-orcamento`).
   **Não** marque "Add README" (o projeto já tem arquivos).
2. Copie a URL que o GitHub mostra, algo como:
   `https://github.com/SEU_USUARIO/seduc-orcamento.git`

## 3. Enviar o projeto (rode dentro da pasta `sistema_orcamento`)
O repositório local já foi inicializado e commitado. Falta só apontar para o
seu GitHub e enviar:

```powershell
git remote add origin https://github.com/SEU_USUARIO/seduc-orcamento.git
git branch -M main
git push -u origin main
```
(O GitHub vai pedir login/senha ou token na primeira vez.)

## 4. Publicar no Render
1. Acesse <https://dashboard.render.com> → **New +** → **Blueprint**.
2. Conecte sua conta GitHub e selecione o repositório `seduc-orcamento`.
3. O Render lê o `render.yaml`, mostra o serviço **seduc-orcamento** → **Apply**.
4. Aguarde o build (instala as dependências) e o deploy.
5. Pronto: o sistema fica numa URL pública `https://seduc-orcamento.onrender.com`.

## 5. Atualizações futuras
Qualquer mudança é publicada sozinha ao enviar para o GitHub:
```powershell
git add -A
git commit -m "ajustes"
git push
```

---

### Alternativa sem Blueprint (manual)
Se preferir não usar o `render.yaml`: **New +** → **Web Service** → conecte o
repo e configure://
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
- **Runtime:** Python 3 · **Python Version:** 3.12.6
