# bot.py (versão final estável)
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from datetime import datetime
import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SENHA = os.getenv("SENHA")

ESTOQUE_FILE = "estoque.csv"
LOG_FILE = "log.csv"

usuarios_autorizados = set()

menu_admin = ReplyKeyboardMarkup([
    ["📦 Estoque"],
    ["➕ Entrada", "➖ Saída"],
    ["🆕 Novo Produto", "❌ Remover Produto"],
    ["📊 Relatório"]
], resize_keyboard=True)

menu_user = ReplyKeyboardMarkup([
    ["🔐 Login"],
    ["📦 Estoque"],
    ["📊 Relatório"]
], resize_keyboard=True)

def is_admin(update):
    return str(update.message.chat_id) == str(CHAT_ID)

def autorizado(user_id):
    return user_id in usuarios_autorizados or str(user_id) == str(CHAT_ID)

def carregar_estoque():
    if not os.path.exists(ESTOQUE_FILE):
        pd.DataFrame(columns=["produto", "quantidade"]).to_csv(ESTOQUE_FILE, index=False)
    return pd.read_csv(ESTOQUE_FILE)

def salvar_estoque(df):
    df.to_csv(ESTOQUE_FILE, index=False)

def salvar_log(registro):
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=["data","produto","quantidade","tipo","turno"]).to_csv(LOG_FILE, index=False)
    log = pd.read_csv(LOG_FILE)
    log = pd.concat([log, pd.DataFrame([registro])])
    log.to_csv(LOG_FILE, index=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if is_admin(update):
        await update.message.reply_text("👑 Bem-vindo ADMIN", reply_markup=menu_admin)
    else:
        await update.message.reply_text("🔐 Faça login", reply_markup=menu_user)

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["login"] = True
    await update.message.reply_text("Digite a senha:")

async def estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update.message.chat_id):
        return
    df = carregar_estoque()
    texto = "📦 ESTOQUE:\n\n"
    for _, row in df.iterrows():
        texto += f"{row['produto']}: {row['quantidade']}\n"
    await update.message.reply_text(texto)

def botoes_produtos(df, acao):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(p, callback_data=f"{acao}|{p}")]
        for p in df["produto"]
    ])

async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    context.user_data.clear()
    df = carregar_estoque()
    await update.message.reply_text("Selecione produto:", reply_markup=botoes_produtos(df, "entrada"))

async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    context.user_data.clear()
    df = carregar_estoque()
    await update.message.reply_text("Selecione produto:", reply_markup=botoes_produtos(df, "saida"))

async def novo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    context.user_data.clear()
    context.user_data["acao"] = "novo"
    await update.message.reply_text("Digite o nome do produto:")

async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    context.user_data.clear()
    df = carregar_estoque()
    await update.message.reply_text("Selecione produto:", reply_markup=botoes_produtos(df, "remover"))

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    acao, produto = query.data.split("|")

    if acao == "remover":
        df = carregar_estoque()
        df = df[df["produto"] != produto]
        salvar_estoque(df)
        await query.edit_message_text(f"❌ {produto} removido")
        return

    context.user_data["produto"] = produto
    context.user_data["acao"] = acao

    if acao == "saida":
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("Turno A", callback_data="turno|A")],
            [InlineKeyboardButton("Turno B", callback_data="turno|B")],
            [InlineKeyboardButton("Turno C", callback_data="turno|C")]
        ])
        await query.edit_message_text("Selecione o turno:", reply_markup=teclado)
    else:
        await query.edit_message_text(f"Digite quantidade para {produto}:")

async def callback_turno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, turno = query.data.split("|")
    context.user_data["turno"] = turno
    await query.edit_message_text(f"Turno {turno} selecionado.\nDigite a quantidade:")

async def processar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    user_id = update.message.chat_id

    if context.user_data.get("login"):
        if texto == SENHA:
            usuarios_autorizados.add(user_id)
            await update.message.reply_text("✅ Acesso liberado", reply_markup=menu_user)
        else:
            await update.message.reply_text("❌ Senha incorreta")
        context.user_data.clear()
        return

    if not autorizado(user_id):
        return

    if texto in ["📦 estoque", "📊 relatório"]:
        return

    if context.user_data.get("acao") == "novo":
        df = carregar_estoque()
        df = pd.concat([df, pd.DataFrame([{"produto": texto, "quantidade": 0}])])
        salvar_estoque(df)
        await update.message.reply_text("✅ Produto criado")
        context.user_data.clear()
        return

    if "produto" in context.user_data:
        try:
            qtd = int(texto)
        except:
            await update.message.reply_text("Digite um número válido")
            return

        produto = context.user_data["produto"]
        acao = context.user_data["acao"]
        turno = context.user_data.get("turno", "-")

        df = carregar_estoque()
        idx = df[df["produto"] == produto].index[0]

        if acao == "entrada":
            df.at[idx, "quantidade"] += qtd
            tipo = "entrada"
        else:
            df.at[idx, "quantidade"] -= qtd
            tipo = "saida"

        salvar_estoque(df)

        salvar_log({
            "data": datetime.now(),
            "produto": produto,
            "quantidade": qtd,
            "tipo": tipo,
            "turno": turno
        })

        await update.message.reply_text("✅ Operação registrada")
        context.user_data.clear()

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update.message.chat_id):
        return
    df = pd.read_csv(LOG_FILE)
    await update.message.reply_text(df.tail(20).to_string())

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Regex("Login"), login))
app.add_handler(MessageHandler(filters.Regex("Estoque"), estoque))
app.add_handler(MessageHandler(filters.Regex("Entrada"), entrada))
app.add_handler(MessageHandler(filters.Regex("Saída"), saida))
app.add_handler(MessageHandler(filters.Regex("Novo Produto"), novo))
app.add_handler(MessageHandler(filters.Regex("Remover Produto"), remover))
app.add_handler(MessageHandler(filters.Regex("Relatório"), relatorio))

app.add_handler(CallbackQueryHandler(callback, pattern="^(entrada|saida|remover)\|"))
app.add_handler(CallbackQueryHandler(callback_turno, pattern="^turno\|"))

app.add_handler(MessageHandler(filters.TEXT, processar))

app.run_polling()
