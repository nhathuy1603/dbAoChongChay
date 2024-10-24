from flask import Flask, request, jsonify, g
import mysql.connector
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

db_config = {
    'user': os.environ['MYSQL_USER'],
    'password': os.environ['MYSQL_PASSWORD'],
    'host': os.environ['MYSQL_HOST'],
    'port': int(os.environ['MYSQL_PORT']),
    'database': os.environ['MYSQL_DATABASE']
}

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(**db_config)
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/data', methods=['POST'])
def receive_data():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    data = request.json

    required_fields = ['building_id', 'floor_number', 'room_number', 'temperature', 'heart_rate', 'gas_concentration', 'user_status', 'uuid']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        cursor.close()
        return jsonify({"message": f"Thiếu các trường: {', '.join(missing_fields)}"}), 400

    building_id = data['building_id']
    floor_number = data['floor_number']
    room_number = data['room_number']
    temperature = data['temperature']
    heart_rate = data['heart_rate']
    gas_concentration = data['gas_concentration']
    user_status = data['user_status']
    uuid = data['uuid']

    # Kiểm tra xem uuid có tồn tại không
    cursor.execute("SELECT * FROM fireproof_jacket WHERE uuid = %s", (uuid,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        return jsonify({"message": "Không tìm thấy uuid"}), 404

    # Kiểm tra xem floor_number có tồn tại không
    cursor.execute("SELECT * FROM floor WHERE building_id = %s AND floor_number = %s", (building_id, floor_number))
    floor_result = cursor.fetchone()

    if not floor_result:
        cursor.close()
        return jsonify({"message": "floor_number không tồn tại"}), 404

    # Kiểm tra xem room_number có tồn tại không
    cursor.execute("SELECT * FROM room WHERE floor_id = %s AND room_number = %s", (floor_result['id'], room_number))
    room_result = cursor.fetchone()

    if not room_result:
        cursor.close()
        return jsonify({"message": "room_number không tồn tại"}), 404

    # Cập nhật dữ liệu nếu uuid, floor_number và room_number tồn tại
    cursor.execute("""
        UPDATE fireproof_jacket 
        SET building_id = %s, floor_number = %s, room_number = %s, temperature = %s, heart_rate = %s, gas_concentration = %s, user_status = %s
        WHERE uuid = %s
    """, (building_id, floor_number, room_number, temperature, heart_rate, gas_concentration, user_status, uuid))

    db.commit()
    cursor.close()

    return jsonify({"status": "thành công"}), 200

@app.route('/data', methods=['GET'])
def get_data():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    page = request.args.get('page')
    fuc = request.args.get('fuc')
    building_id = request.args.get('building_id')

    if not page:
        # Trả về tất cả thông tin của các áo chống cháy
        cursor.execute("SELECT * FROM fireproof_jacket")
        fireproof_jackets = cursor.fetchall()
        cursor.close()
        return jsonify(fireproof_jackets), 200

    if page == 'trangchu':
        if fuc == 'map':
            # Trả về thông tin của tất cả tòa nhà
            cursor.execute("""
                SELECT 
                    building.*,
                    (SELECT COUNT(*) FROM floor WHERE floor.building_id = building.id) AS total_floors,
                    (SELECT COUNT(*) FROM room WHERE room.floor_id IN (SELECT id FROM floor WHERE floor.building_id = building.id)) AS total_rooms,
                    (SELECT COUNT(*) FROM fireproof_jacket WHERE fireproof_jacket.building_id = building.id) AS total_people
                FROM building
            """)
            buildings = cursor.fetchall()
            cursor.close()
            return jsonify(buildings), 200
        else:
            # Trả về số lượng tòa nhà, áo chống cháy, trạng thái cảnh báo, trạng thái nguy hiểm
            cursor.execute("SELECT COUNT(*) AS total_buildings FROM building")
            total_buildings = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) AS total_jackets FROM fireproof_jacket")
            total_jackets = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) AS alert_status FROM fireproof_jacket WHERE user_status = 1")
            alert_status = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) AS danger_status FROM fireproof_jacket WHERE user_status = 2")
            danger_status = cursor.fetchone()

            cursor.close()

            result = {
                "total_buildings": total_buildings['total_buildings'],
                "total_jackets": total_jackets['total_jackets'],
                "alert_status": alert_status['alert_status'],
                "danger_status": danger_status['danger_status']
            }

            return jsonify(result), 200

    elif page == 'details' and building_id:
        # Trả về thông tin chi tiết của từng tòa nhà
        cursor.execute("SELECT * FROM floor WHERE building_id = %s", (building_id,))
        floors = cursor.fetchall()

        building_details = []
        for floor in floors:
            cursor.execute("SELECT * FROM room WHERE floor_id = %s", (floor['id'],))
            rooms = cursor.fetchall()

            # Loại bỏ trường floor_id từ mỗi phòng
            for room in rooms:
                room.pop('floor_id', None)

            floor_details = {
                "floor_number": floor['floor_number'],
                "total_rooms": len(rooms),
                "rooms": rooms
            }
            building_details.append(floor_details)

        cursor.close()
        return jsonify(building_details), 200

    cursor.close()
    return jsonify({"message": "Invalid request"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
