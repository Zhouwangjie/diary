from flask import Flask, request, jsonify
import pymysql
from flask_cors import CORS
from openai import OpenAI
from config import API_KEY
from datetime import datetime, timedelta
import sqlite3
import json

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置OpenAI客户端
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

# 连接 MySQL 数据库
db = pymysql.connect(
    host="localhost",
    user="root",  # 你的 MySQL 用户名
    password="1234",  # 你的 MySQL 密码
    database="diary",
    charset="utf8mb4"
)

# 提交日记内容
@app.route('/submit', methods=['POST'])
def submit_diary():
    try:
        print("开始处理提交请求...")
        data = request.json  # 获取前端传来的 JSON 数据
        content = data.get("content")
        time = data.get("time")  # 传入的日记时间
        print(f"接收到的数据：content长度={len(str(content))}, time={time}")
        system_content = """
            你是一名资深的心理专家，擅长从用户输入的文字中分析其情绪状态，并提供合理的心理反馈。你的任务是基于用户的文字内容，判断Color_Index，并生成相应的心理反馈。

            ## 任务要求：
            1. 解析用户输入的文本，从中提取情绪信息。
            2. 根据情绪信息判断Color_Index的值：
            - 0：用户心情不好
            - 1：用户情绪平静
            - 2：用户心情较好
            3. 生成适当的心理反馈，并以JSON格式输出，格式如下：
            {
                "Color_Index": <0/1/2>,
                "Response_Content": "<心理反馈内容>"
            }
        """

        if not content or not time:
            return jsonify({"error": "内容和时间不能为空"}), 400

        # 调用DeepSeek API获取回复
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": content},
            ],
            response_format={
                'type': 'json_object'
            }
        )
        print("DeepSeek API响应：", response)
        response_json = response.choices[0].message.content
        print("API返回的JSON内容：", response_json)
        try:
            response_data = json.loads(response_json)  # 使用json.loads替代eval，更安全
            agent_content = response_data['Response_Content']
            emotion = response_data['Color_Index']
            print(f"解析后的数据：emotion={emotion}, agent_content长度={len(str(agent_content))}")
        except json.JSONDecodeError as je:
            print(f"JSON解析错误：{str(je)}")
            raise
        except KeyError as ke:
            print(f"缺少必要的键：{str(ke)}")
            raise

        try:
            cursor = db.cursor()
            sql = "INSERT INTO diary_day (content, time, agent_content, emotion) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (content, time, agent_content, emotion))
            db.commit()
            print("数据库插入成功")
        except pymysql.Error as e:
            print(f"数据库错误：{str(e)}")
            db.rollback()
            raise

        return jsonify({"message": "日记保存成功！"}), 201
    except Exception as e:
        error_message = f"错误详情：{str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

# 获取所有日记
@app.route('/diary', methods=['GET'])
def get_diary():
    try:
        cursor = db.cursor()
        sql = "SELECT id, content, time, created_time, modify_time, agent_content, emotion FROM diary_day ORDER BY created_time DESC"
        cursor.execute(sql)
        result = cursor.fetchall()

        diaries = [
            {
                "id": row[0],
                "content": row[1],
                "time": row[2],
                "created_time": row[3],
                "modify_time": row[4],
                "agent_content": row[5],
                "emotion": row[6]
            }
            for row in result
        ]

        return jsonify(diaries), 200
    except Exception as e:
        error_message = f"错误详情：{str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

# 添加删除日记的路由
@app.route('/diary/<int:diary_id>', methods=['DELETE'])
def delete_diary(diary_id):
    try:
        cursor = db.cursor()
        
        # 检查日记是否存在
        cursor.execute('SELECT id FROM diary_day WHERE id = %s', (diary_id,))
        if not cursor.fetchone():
            return jsonify({'error': '日记不存在'}), 404
        
        # 删除日记
        cursor.execute('DELETE FROM diary_day WHERE id = %s', (diary_id,))
        db.commit()
        
        return jsonify({'message': '删除成功'})
    
    except pymysql.Error as e:
        db.rollback()
        return jsonify({'error': f'数据库错误：{str(e)}'}), 500

# 添加收信路由
@app.route('/collect_month', methods=['POST'])
def collect_month():
    try:
        data = request.json
        year = data.get('year')
        month = data.get('month')  # 0-11
        
        print(f"\n开始处理 {year}年{month + 1}月 的收信请求...")
        
        # 获取指定月份的所有日记内容和日期
        cursor = db.cursor()
        sql = """
            SELECT created_time, content, DAY(created_time) as day_of_month
            FROM diary_day 
            WHERE YEAR(created_time) = %s 
            AND MONTH(created_time) = %s 
            ORDER BY created_time
        """
        cursor.execute(sql, (year, month + 1))
        diary_entries = cursor.fetchall()
        
        if not diary_entries:
            print("没有找到该月的日记内容")
            return jsonify({'error': '该月没有日记内容'}), 404

        # 收集所有日期并用逗号连接
        days = ','.join(str(entry[2]) for entry in diary_entries)
        print(f"该月写日记的日期: {days}")

        # 将日记内容组合成一个字符串
        diary_text = "\n".join([
            f"时间：{entry[0]}\n内容：{entry[1]}" 
            for entry in diary_entries
        ])
        print("\n发送给 DeepSeek 的日记内容:")
        print("=" * 50)
        print(diary_text)
        print("=" * 50)

        # 调用 DeepSeek API 进行分析
        system_content = """
            你是一个我的挚友，常年写信交流，请根据用户最近的日记内容，生成一封温暖的回信。
            同时判断这个月的整体情绪状态，用month_emotion表示：
            - 0：整体心情不好
            - 1：整体情绪平静
            - 2：整体心情较好

            请以JSON格式输出，格式如下：
            {
                "content": "<回信内容>",
                "month_emotion": <0/1/2>
            }
        """

        print("\n调用 DeepSeek API...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": diary_text},
            ],
            response_format={
                'type': 'json_object'
            }
        )

        response_json = response.choices[0].message.content
        print("\nDeepSeek API 返回的原始响应:")
        print("=" * 50)
        print(response_json)
        print("=" * 50)

        response_data = json.loads(response_json)
        print("\n解析后的数据:")
        print(f"情绪值: {response_data['month_emotion']}")
        print(f"回信内容: {response_data['content']}")
        
        # 保存到 diary_month 表
        sql = """
            INSERT INTO diary_month (content, month, day, create_time, month_emotion) 
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
        """
        cursor.execute(sql, (
            response_data['content'],
            month + 1,
            days,
            response_data['month_emotion']
        ))
        db.commit()
        print("\n数据已成功保存到数据库")

        return jsonify({
            'message': '收信成功',
            'content': response_data['content']
        })

    except Exception as e:
        db.rollback()
        error_message = f"错误详情：{str(e)}"
        print(f"\n处理收信请求时出错: {error_message}")
        return jsonify({"error": error_message}), 500

# 获取所有信件
@app.route('/letters', methods=['GET'])
def get_letters():
    try:
        cursor = db.cursor()
        sql = """
            SELECT id, content, month, day, create_time, month_emotion 
            FROM diary_month 
            ORDER BY create_time DESC
        """
        cursor.execute(sql)
        result = cursor.fetchall()

        letters = [
            {
                "id": row[0],
                "content": row[1],
                "month": row[2],
                "day": row[3],
                "create_time": row[4],
                "month_emotion": row[5]
            }
            for row in result
        ]

        return jsonify(letters), 200
    except Exception as e:
        error_message = f"错误详情：{str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

# 添加删除信件的路由
@app.route('/letters/<int:letter_id>', methods=['DELETE'])
def delete_letter(letter_id):
    try:
        cursor = db.cursor()
        
        # 检查信件是否存在
        cursor.execute('SELECT id FROM diary_month WHERE id = %s', (letter_id,))
        if not cursor.fetchone():
            return jsonify({'error': '信件不存在'}), 404
        
        # 删除信件
        cursor.execute('DELETE FROM diary_month WHERE id = %s', (letter_id,))
        db.commit()
        
        return jsonify({'message': '删除成功'})
    
    except Exception as e:
        db.rollback()
        error_message = f"错误详情：{str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

# 添加检查今日是否已写日记的路由
@app.route('/check_today', methods=['GET'])
def check_today():
    try:
        cursor = db.cursor()
        # 获取今天的日记
        sql = """
            SELECT created_time 
            FROM diary_day 
            WHERE DATE(created_time) = CURDATE()
            LIMIT 1
        """
        cursor.execute(sql)
        result = cursor.fetchone()
        
        if result:
            # 如果今天已写日记，计算下次可写作时间
            next_time = datetime.combine(
                datetime.now().date() + timedelta(days=1), 
                datetime.min.time()
            )
            return jsonify({
                'can_write': False,
                'next_time': next_time.strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            return jsonify({'can_write': True})

    except Exception as e:
        error_message = f"错误详情：{str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
