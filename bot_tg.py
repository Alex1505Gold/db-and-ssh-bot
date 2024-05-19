from dotenv import load_dotenv
from pathlib import Path
import os
import paramiko
import logging
import re
from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import psycopg2
from psycopg2 import Error

dotenv_path = Path('.env')
load_dotenv(dotenv_path=dotenv_path)

TOKEN = os.getenv('BOT_TOKEN')


# Подключаем логирование
logging.basicConfig(
    filename='logfile.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

def sshExecute(command : str, db_connect = False):
    host = os.getenv('HOST')
    port = os.getenv('PORT')
    username = os.getenv('USER')
    password = os.getenv('PASSWORD')
    if db_connect:
        host = os.getenv('DB_HOST')
        port = os.getenv('DB_PORT_SSH')
        username = os.getenv('DB_USER_SSH')
        password = os.getenv('DB_PASSWORD_SSH')

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=username, password=password, port=port)
    stdin, stdout, stderr = client.exec_command(command)
    data = stdout.read() + stderr.read()
    client.close()
    data = str(data).replace('\\n', '\n').replace('\\t', '\t')[2:-1]
    return data

def sqlGet(command : str):
    connection = None
    data = None
    try:
        connection = psycopg2.connect(user=os.getenv('DB_USER'),
                                    password=os.getenv('DB_PASSWORD'),
                                    host = os.getenv('DB_HOST'),
                                    port=os.getenv('DB_PORT'), 
                                    database=os.getenv('DB_NAME'))

        cursor = connection.cursor()
        cursor.execute(command)
        data = cursor.fetchall()
        logging.info("Команда успешно выполнена")
    except (Exception, Error) as error:
        logging.error("Ошибка при работе с PostgreSQL: %s", error)
    finally:
        if connection is not None:
            cursor.close()
            connection.close()
    return data

def sqlExecute(command : str):
    connection = None
    success = True
    try:
        connection = psycopg2.connect(user=os.getenv('DB_USER'),
                                    password=os.getenv('DB_PASSWORD'),
                                    host = os.getenv('DB_HOST'),
                                    port=os.getenv('DB_PORT'), 
                                    database=os.getenv('DB_NAME'))

        cursor = connection.cursor()
        cursor.execute(command)
        connection.commit() 
        logging.info("Команда успешно выполнена")
    except (Exception, Error) as error:
        logging.error("Ошибка при работе с PostgreSQL: %s", error)
        success = False
    finally:
        if connection is not None:
            cursor.close()
            connection.close()
    return success

def start(update: Update, context):
    user = update.effective_user
    update.message.reply_text(f'Привет {user.full_name}!')


def helpCommand(update: Update, context):
    update.message.reply_text('Доступны следующие команды:\n\
                              /find_email\n/find_phone_numbers\n/verify_password\n\
                              /get_release\n/get_uname\n/get_uptime\n/get_df\n/get_free\n\
                              /get_mpstat\n/get_w\n/get_auths\n/get_critical\n/get_ps\n\
                              /get_ss\n/get_apt_list\n/get_services')


def findPhoneNumbersCommand(update: Update, context):
    update.message.reply_text('Введите текст для поиска телефонных номеров: ')

    return 'find_phone_numbers'


def findPhoneNumbers (update: Update, context):
    user_input = update.message.text 

    phoneNumRegex = re.compile(r'(?:\+7|8)(?: \(|\(| |-|)\d{3}(?:\) |\)| |-|)\d{3}(?:-| |)\d{2}(?:-| |)\d{2}')

    phoneNumberList = phoneNumRegex.findall(user_input)

    if not phoneNumberList: 
        update.message.reply_text('Телефонные номера не найдены')
        return ConversationHandler.END
    
    phoneNumbers = ''
    for i in range(len(phoneNumberList)):
        phoneNumbers += f'{i+1}. {phoneNumberList[i]}\n'

    context.user_data['phone_list'] = phoneNumberList
    update.message.reply_text(phoneNumbers) 
    update.message.reply_text('Добавить в бд?: \n(да/нет) ')
    return 'phone_sql'

def phoneSQL(update: Update, context):
    user_input = update.message.text 
    if user_input == 'да':
        phoneList = context.user_data['phone_list']
        command = 'INSERT INTO phone_numbers (phone_number) VALUES'
        for i in range(len(phoneList)):
            command += f'(\'{phoneList[i]}\'),'
        command = command[:-1]
        command += ';'
        res = sqlExecute(command)
        if res:
            update.message.reply_text('Номера телефонов успешно добавлены ')
        else:
            update.message.reply_text('Произошла ошибка при работе с БД ')
        return ConversationHandler.END

    elif user_input == 'нет':
        return ConversationHandler.END
    
    update.message.reply_text('Команда не распознана ')
    return ConversationHandler.END

def getPhoneNumbers(update: Update, context):
    data = sqlGet('SELECT * FROM phone_numbers;')
    if data is not None:
        response = ''
        for row in data:
            response += 'ID: ' + str(row[0]) + ' phone_number: ' + str(row[1]) + '\n'
        update.message.reply_text(response)
        return ConversationHandler.END
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def findEmailsCommand(update: Update, context):
    update.message.reply_text('Введите текст для поиска email: ')

    return 'find_email'

def findEmails (update: Update, context):
    user_input = update.message.text 

    emailRegex = re.compile(r'\w+\@[a-zA-Z]+.[a-zA-Z]+') 

    emailList = emailRegex.findall(user_input) 

    if not emailList: 
        update.message.reply_text('Email\'ы не найдены')
        return ConversationHandler.END
    
    emails = '' 
    for i in range(len(emailList)):
        emails += f'{i+1}. {emailList[i]}\n' 
    context.user_data['email_list'] = emailList
    update.message.reply_text(emails) 
    update.message.reply_text('Добавить в бд?: \n(да/нет) ')
    return 'email_sql'

def emailSQL(update: Update, context):
    user_input = update.message.text 
    if user_input == 'да':
        emailList = context.user_data['email_list']
        command = 'INSERT INTO emails (email) VALUES'
        for i in range(len(emailList)):
            command += f'(\'{emailList[i]}\'),'
        command = command[:-1]
        command += ';'
        res = sqlExecute(command)
        if res:
            update.message.reply_text('Email\'ы успешно добавлены ')
        else:
            update.message.reply_text('Произошла ошибка при работе с БД ')
        return ConversationHandler.END

    elif user_input == 'нет':
        return ConversationHandler.END
    
    update.message.reply_text('Команда не распознана ')
    return ConversationHandler.END

def getEmails(update: Update, context):
    data = sqlGet('SELECT * FROM emails;')
    if data is not None:
        response = ''
        for row in data:
            response += 'ID: ' + str(row[0]) + ' email: ' + str(row[1]) + '\n'
        update.message.reply_text(response)
        return ConversationHandler.END
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def verifyPasswordCommand(update: Update, context):
    update.message.reply_text('Введите пароль: ')

    return 'verify_password'

def verifyPassword(update: Update, context):
    user_input = update.message.text 

    passwordRegex = re.compile(r'^(?=.*[0-9])(?=.*[!@#$%^&*()])(?=.*[a-z])(?=.*[A-Z])[0-9a-zA-Z!@#$%^&*()]{8,}$') 

    passwordCheck = passwordRegex.search(user_input) 
    passwordVerdict = ''
    if passwordCheck is None: 
        passwordVerdict = 'Пароль простой, либо не соответствует требованиям'
    else:
        passwordVerdict = 'Пароль сложный'
        
    update.message.reply_text(passwordVerdict) 
    return ConversationHandler.END 

def getRelease(update: Update, context):
    data = sshExecute('lsb_release -a')
    update.message.reply_text(data) 
    return ConversationHandler.END 

def getUname(update: Update, context):
    data = sshExecute('hostnamectl')
    update.message.reply_text(data) 
    return ConversationHandler.END 

def getUptime(update: Update, context):
    data = sshExecute('uptime')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getDf(update: Update, context):
    data = sshExecute('df -Th')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getFree(update: Update, context):
    data = sshExecute('free -h')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getMpstat(update: Update, context):
    data = sshExecute('mpstat')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getW(update: Update, context):
    data = sshExecute('w')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getAuth(update: Update, context):
    data = sshExecute('last -10')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getCritical(update: Update, context):
    data = sshExecute('journalctl -p crit -n 5')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getPs(update: Update, context):
    data = sshExecute('ps -A u | head -n 10')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getSs(update: Update, context):
    data = sshExecute('ss | head -n 10')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getAptListCommand(update: Update, context):
    update.message.reply_text('Введите название пакета либо --all: ')

    return 'get_apt_list'

def getAptList(update: Update, context):
    user_input = update.message.text.split('\n')
    command =''
    if user_input[0] == '--all':
        command = 'apt list | head -n 12'
    else:
        injectionRegex = re.compile(r'[ |;&]') 
        injection = injectionRegex.search(user_input[0]) 
        if injection is not None:
            update.message.reply_text('Недопустимые символы в имени пакета') 
            return ConversationHandler.END
        command = f'apt list | grep {user_input[0]} | head -n 12'
    data = sshExecute(command)
    update.message.reply_text(data) 
    return ConversationHandler.END

def getServices(update: Update, context):
    data = sshExecute('systemctl list-units --type=service | head -n 11')
    update.message.reply_text(data) 
    return ConversationHandler.END

def getReplLogs(update: Update, context):
    data = sshExecute('cat /var/log/postgresql/postgresql-15-main.log | grep -i \'replication\' | tail -n 10', True)
    update.message.reply_text(data) 
    return ConversationHandler.END

def echo(update: Update, context):
    update.message.reply_text(update.message.text)


def main():
    updater = Updater(TOKEN, use_context=True)

    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher

    # Обработчик диалога
    convHandlers = ConversationHandler(
        entry_points=[CommandHandler('find_phone_numbers', findPhoneNumbersCommand),
                      CommandHandler('find_email', findEmailsCommand),
                      CommandHandler('verify_password', verifyPasswordCommand),
                      CommandHandler('get_apt_list', getAptListCommand),
                      ],
        states={
            'find_phone_numbers': [MessageHandler(Filters.text & ~Filters.command, findPhoneNumbers)],
            'find_email': [MessageHandler(Filters.text & ~Filters.command, findEmails)],
            'verify_password': [MessageHandler(Filters.text & ~Filters.command, verifyPassword)],
            'get_apt_list': [MessageHandler(Filters.text & ~Filters.command, getAptList)],
            'email_sql': [MessageHandler(Filters.text & ~Filters.command, emailSQL)],
            'phone_sql': [MessageHandler(Filters.text & ~Filters.command, phoneSQL)],
        },
        fallbacks=[]
    )
		
	# Регистрируем обработчики команд
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", helpCommand))
    dp.add_handler(CommandHandler("get_release", getRelease))
    dp.add_handler(CommandHandler("get_uname", getUname))
    dp.add_handler(CommandHandler("get_uptime", getUptime))
    dp.add_handler(CommandHandler("get_df", getDf))
    dp.add_handler(CommandHandler("get_free", getFree))
    dp.add_handler(CommandHandler("get_mpstat", getMpstat))
    dp.add_handler(CommandHandler("get_w", getW))
    dp.add_handler(CommandHandler("get_auths", getAuth))
    dp.add_handler(CommandHandler("get_critical", getCritical))
    dp.add_handler(CommandHandler("get_ps", getPs))
    dp.add_handler(CommandHandler("get_ss", getSs))
    dp.add_handler(CommandHandler("get_services", getServices))
    dp.add_handler(CommandHandler("get_repl_logs", getReplLogs))
    dp.add_handler(CommandHandler("get_phone_numbers", getPhoneNumbers))
    dp.add_handler(CommandHandler("get_email", getEmails))
    dp.add_handler(convHandlers)
		
	# Регистрируем обработчик текстовых сообщений
    # dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))
		
	# Запускаем бота
    updater.start_polling()

	# Останавливаем бота при нажатии Ctrl+C
    updater.idle()


if __name__ == '__main__':
    main()
