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

def sshExecute(command : str):
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
                                    database='music_lover')

        cursor = connection.cursor()
        cursor.execute(command)
        data = cursor.fetchall()
        logging.info("Command executed successfuly")
    except (Exception, Error) as error:
        logging.error("Error with PostgreSQL: %s", error)
    finally:
        if connection is not None:
            cursor.close()
            connection.close()
    return data

def start(update: Update, context):
    user = update.effective_user
    update.message.reply_text(f'Привет {user.full_name}!')

def helpCommand(update: Update, context):
    update.message.reply_text('Доступны следующие команды:\n\
        /show_all - весь каталог\n\
        /find_genre - поиск по жанрам\n\
        /find_artist - поиск по исполнителям\n\
        /find_media - поиск по носителям\n\
        /find_album - поиск по альбомам\n\
        ')

def getReplLogs(update: Update, context):
    data = sshExecute('cat /var/log/postgresql/postgresql-15-main.log | grep -i \'replication\' | tail -n 10')
    update.message.reply_text(data) 
    return ConversationHandler.END

def showAll(update: Update, context):
    data = sqlGet('SELECT \
	            a.id, a.media_type AS media, au.author_name AS artist, \
	            ai.album_name AS album, ai.album_genre AS genre, b.stand_number AS stand, \
	            b.shelf_number AS shelf, b.box_on_shelf_number AS box \
                FROM \
	            albums a \
	            JOIN boxes b ON b.id = a.id_box \
	            JOIN album_info ai ON ai.id = a.id_album_info \
	            JOIN authors au ON au.id = ai.id_author;')
    if data is not None:
        response = ''
        for row in data:
            response += 'ID: ' + str(row[0]) + ', media type: ' + str(row[1]) + '\n' \
            + 'artist: ' + str(row[2]) + ', album: ' + str(row[3]) + ', genre: ' + str(row[4]) + '\n' \
            + 'Find at: stand ' + str(row[5]) + ', shelf ' + str(row[6]) + ', box: ' + str(row[7]) + '\n'
        update.message.reply_text(response)
        return ConversationHandler.END
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def userInputHandler(criteria : str, user_input):
    data = None
    injectionRegex = re.compile(r'(-- -)|(--)') 

    injectionCheck = injectionRegex.search(user_input)
    if injectionCheck is None:
        data = sqlGet(f'SELECT \
	                a.id, a.media_type AS media, au.author_name AS artist, \
	                ai.album_name AS album, ai.album_genre AS genre, b.stand_number AS stand, \
	                b.shelf_number AS shelf, b.box_on_shelf_number AS box \
                    FROM \
	                albums a \
	                JOIN boxes b ON b.id = a.id_box \
	                JOIN album_info ai ON ai.id = a.id_album_info \
	                JOIN authors au ON au.id = ai.id_author\
                    WHERE {criteria} = \'{user_input}\';')
    
    return data

def findGenreCommand(update: Update, context):
    data = sqlGet('SELECT album_genre FROM album_info;')
    if data is not None:
        response = 'В каталоге представлены следующие жанры:\n'
        for row in data:
            response += str(row[0]) + '\n'
        update.message.reply_text(response)
        return 'find_genre_state'
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def findGenre(update: Update, context):
    user_input = update.message.text
    data = userInputHandler('ai.album_genre', user_input)
    if data is not None:
        response = ''
        for row in data:
            response += 'ID: ' + str(row[0]) + ', media type: ' + str(row[1]) + '\n' \
            + 'artist: ' + str(row[2]) + ', album: ' + str(row[3]) + '\n' \
            + 'Find at: stand ' + str(row[5]) + ', shelf ' + str(row[6]) + ', box: ' + str(row[7]) + '\n'
        update.message.reply_text(response)
        return ConversationHandler.END
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def findArtistCommand(update: Update, context):
    data = sqlGet('SELECT author_name FROM authors;')
    if data is not None:
        response = 'В каталоге представлены следующие исполнители: \n'
        for row in data:
            response += str(row[0]) + '\n'
        update.message.reply_text(response)
        return 'find_artist_state'
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def findArtist(update: Update, context):
    user_input = update.message.text
    data = userInputHandler('au.author_name', user_input)
    if data is not None:
        response = ''
        for row in data:
            response += 'ID: ' + str(row[0]) + ', media type: ' + str(row[1]) + '\n' \
            + 'genre: ' + str(row[4]) + ', album: ' + str(row[3]) + '\n' \
            + 'Find at: stand ' + str(row[5]) + ', shelf ' + str(row[6]) + ', box: ' + str(row[7]) + '\n'
        update.message.reply_text(response)
        return ConversationHandler.END
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def findMediaCommand(update: Update, context):
    update.message.reply_text('В каталоге представлены следующие виды носителей\n\
        CD\nvinyl\ncassete tape ')
    return 'find_media_state'

def findMedia(update: Update, context):
    user_input = update.message.text
    data = userInputHandler('a.media_type', user_input)
    if data is not None:
        response = ''
        for row in data:
            response += 'ID: ' + str(row[0]) + ', artist: ' + str(row[2]) + '\n' \
            + 'genre: ' + str(row[4]) + ', album: ' + str(row[3]) + '\n' \
            + 'Find at: stand ' + str(row[5]) + ', shelf ' + str(row[6]) + ', box: ' + str(row[7]) + '\n'
        update.message.reply_text(response)
        return ConversationHandler.END
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def findAlbumCommand(update: Update, context):
    update.message.reply_text('Ищите конкретный альбом? Введите название: ')
    return 'find_album_state'

def findAlbum(update: Update, context):
    user_input = update.message.text
    data = userInputHandler('ai.album_name', user_input)
    if data is not None:
        response = ''
        for row in data:
            response += 'ID: ' + str(row[0]) + ', media type: ' + str(row[1]) + '\n' \
            + 'artist: ' + str(row[2]) + ', album: ' + str(row[3]) + ', genre: ' + str(row[4]) + '\n' \
            + 'Find at: stand ' + str(row[5]) + ', shelf ' + str(row[6]) + ', box: ' + str(row[7]) + '\n'
        update.message.reply_text(response)
        return ConversationHandler.END
    update.message.reply_text('Произошла ошибка при работе с БД ')
    return ConversationHandler.END

def defaultReply(update: Update, context):
    update.message.reply_text('Чтобы увидеть список доступных команд введите /help')

def main():
    updater = Updater(TOKEN, use_context=True)

    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher

    # Обработчик диалога
    convHandlers = ConversationHandler(
        entry_points=[CommandHandler('find_genre', findGenreCommand),
                      CommandHandler('find_artist', findArtistCommand),
                      CommandHandler('find_media', findMediaCommand),
                      CommandHandler('find_album', findAlbumCommand),
                      ],
        states={
            'find_genre_state': [MessageHandler(Filters.text & ~Filters.command, findGenre)],
            'find_artist_state': [MessageHandler(Filters.text & ~Filters.command, findArtist)],
            'find_media_state': [MessageHandler(Filters.text & ~Filters.command, findMedia)],
            'find_album_state': [MessageHandler(Filters.text & ~Filters.command, findAlbum)],
        },
        fallbacks=[]
    )

	# Регистрируем обработчики команд
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", helpCommand))
    dp.add_handler(CommandHandler("get_repl_logs", getReplLogs))
    dp.add_handler(CommandHandler("show_all", showAll))
    dp.add_handler(convHandlers)
		
	# Регистрируем обработчик текстовых сообщений
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, defaultReply))
		
	# Запускаем бота
    updater.start_polling()

	# Останавливаем бота при нажатии Ctrl+C
    updater.idle()


if __name__ == '__main__':
    main()
