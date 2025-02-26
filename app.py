from flask import Flask, request, jsonify
import pymysql
from flask_cors import CORS
from openai import OpenAI
from config import API_KEY

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
            import json
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
