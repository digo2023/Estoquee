import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import time
import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ESTOQUE_FILE = "estoque.csv"
LOG_FILE = "log.csv"

menu = ReplyKeyboardMarkup([
    ["📦 Estoque"],
    ["➕ Entrada", "➖ Saída"],
    ["🆕 Novo Produto", "❌ Remover Produto"],
    ["📊 Relatório"]
], resize_keyboard=True)

def is_admin(update):
    return str(update.message.chat_id) == str(CHAT_ID)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Controle de Estoque - EXPRESS\n\nUso privado.",
        reply_markup=menu
    )

async def estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = pd.read_csv(ESTOQUE_FILE)
    texto = "📦 Estoque:\n\n"
    for _, row in df.iterrows():
        texto += f"{row['produto']}: {row['quantidade']}\n"
    await update.message.reply_text(texto)

async def novo_produto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Sem permissão.")
        return
    context.user_data["acao"] = "novo"
    await update.message.reply_text("Digite o nome do novo produto:")

async def remover_produto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Sem permissão.")
        return
    context.user_data["acao"] = "remover"
    await update.message.reply_text("Digite o nome do produto para remover:")

async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Sem permissão.")
        return
    context.user_data["acao"] = "entrada"
    await update.message.reply_text("Digite: produto quantidade")

async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Sem permissão.")
        return
    context.user_data["acao"] = "saida"
    await update.message.reply_text("Digite: produto quantidade turno(A/B/C)")

async def processar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        acao = context.user_data.get("acao")

        # NOVO PRODUTO
        if acao == "novo":
            produto = update.message.text.strip().lower()
            df = pd.read_csv(ESTOQUE_FILE)

            if produto in df["produto"].values:
                await update.message.reply_text("Produto já existe.")
                return

            df = pd.concat([df, pd.DataFrame([{"produto": produto, "quantidade": 0}])])
            df.to_csv(ESTOQUE_FILE, index=False)

            await update.message.reply_text("✅ Produto cadastrado!", reply_markup=menu)
            return

        # REMOVER PRODUTO
        if acao == "remover":
            produto = update.message.text.strip().lower()
            df = pd.read_csv(ESTOQUE_FILE)

            if produto not in df["produto"].values:
                await update.message.reply_text("Produto não encontrado.")
                return

            df = df[df["produto"] != produto]
            df.to_csv(ESTOQUE_FILE, index=False)

            await update.message.reply_text("❌ Produto removido!", reply_markup=menu)
            return

        # BLOQUEIO PARA NÃO ADMIN
        if not is_admin(update):
            return

        dados = update.message.text.split()
        produto = dados[0]
        qtd = int(dados[1])

        df = pd.read_csv(ESTOQUE_FILE)

        if produto not in df["produto"].values:
            await update.message.reply_text("Produto não existe.")
            return

        idx = df[df["produto"] == produto].index[0]

        if acao == "entrada":
            df.at[idx, "quantidade"] += qtd
            turno = "-"
        else:
            turno = dados[2]
            df.at[idx, "quantidade"] -= qtd

        df.to_csv(ESTOQUE_FILE, index=False)

        log = pd.read_csv(LOG_FILE)
        log = pd.concat([log, pd.DataFrame([{
            "data": pd.Timestamp.now(),
            "turno": turno,
            "produto": produto,
            "quantidade": qtd
        }])])
        log.to_csv(LOG_FILE, index=False)

        await update.message.reply_text("✅ Registrado!", reply_markup=menu)

    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = pd.read_csv(LOG_FILE)

    if df.empty:
        await update.message.reply_text("Sem dados hoje.")
        return

    df["data"] = pd.to_datetime(df["data"])
    hoje = pd.Timestamp.now().date()
    df = df[df["data"].dt.date == hoje]

    texto = "📊 RELATÓRIO DO DIA\n"

    for turno in ["A", "B", "C"]:
        texto += f"\nTurno {turno}:\n"
        df_t = df[df["turno"] == turno]

        for prod in df_t["produto"].unique():
            qtd = df_t[df_t["produto"] == prod]["quantidade"].sum()
            texto += f"{prod}: {qtd}\n"

    await update.message.reply_text(texto)

async def enviar_relatorio(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="📊 Relatório automático ativo.")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Regex("Estoque"), estoque))
app.add_handler(MessageHandler(filters.Regex("Entrada"), entrada))
app.add_handler(MessageHandler(filters.Regex("Saída"), saida))
app.add_handler(MessageHandler(filters.Regex("Novo Produto"), novo_produto))
app.add_handler(MessageHandler(filters.Regex("Remover Produto"), remover_produto))
app.add_handler(MessageHandler(filters.Regex("Relatório"), relatorio))
app.add_handler(MessageHandler(filters.TEXT, processar))

app.job_queue.run_daily(enviar_relatorio, time(hour=22, minute=0))

app.run_polling()
