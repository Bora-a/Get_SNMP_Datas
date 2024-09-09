import subprocess
import time
import mysql.connector
from datetime import datetime

switch_ip = ''
community_string = ''
db_host = ''  
db_user = ''
db_password = ''
db_name = ''

base_oids = {
    'ifInOctets': '1.3.6.1.2.1.2.2.1.10',
    'ifOutOctets': '1.3.6.1.2.1.2.2.1.16',
    'ifInUcastPkts': '1.3.6.1.2.1.2.2.1.11',
    'ifInNUcastPkts': '1.3.6.1.2.1.2.2.1.12',
    'ifInDiscards': '1.3.6.1.2.1.2.2.1.13',
    'ifOutUcastPkts': '1.3.6.1.2.1.2.2.1.17',
    'ifOperStaus': '1.3.6.1.2.1.2.2.1.8',
}

last_values = {key: [0]*24 for key in base_oids.keys()}
last_timestamps = {key: [time.time()]*24 for key in base_oids.keys()}

def get_snmp_data(oid, target, community, port=161):
    try:
        result = subprocess.run(
            ['snmpget', '-v', '2c', '-c', community, target, oid],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        output = result.stdout.strip()
        if 'No Such Instance' in output or 'No Such Object' in output:
            return None

        value = output.split('=')[-1].strip()
        if ':' in value:
            value = value.split(':')[-1].strip()

        return int(''.join(filter(str.isdigit, value)))
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr.strip()}")
        return None
    except ValueError:
        print("ValueError: Could not convert value to integer.")
        return None

def save_to_database(cursor, interface_id, data, timestamp):
    insert_query = """
    INSERT INTO snmp_datas (İnterface_id, ifInOctets, ifOutOctets, ifInUcastPkts, 
                           ifInNUcastPkts, ifInDiscards, ifOutUcastPkts, ifOperStaus, time)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (interface_id, *data, timestamp))

while True:
    try:
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name
        )
        cursor = conn.cursor()

        for interface_id in range(1, 25):
            data = []
            timestamp = time.time()

            for key, base_oid in base_oids.items():
                oid = f"{base_oid}.{interface_id}"
                value = get_snmp_data(oid, switch_ip, community_string)

                if key != "ifOperStaus":
                    last_value = last_values[key][interface_id-1]
                    last_timestamp = last_timestamps[key][interface_id-1]

                    if last_value is not None and value is not None and last_timestamp is not None:
                        value_diff = value - last_value
                        time_diff = timestamp - last_timestamp
                        result = value_diff / time_diff if time_diff != 0 else 0
                    else:
                        result = None
                else:
                    result = value

                data.append(result)
                last_values[key][interface_id-1] = value
                last_timestamps[key][interface_id-1] = timestamp

            date_time = datetime.fromtimestamp(timestamp)
            formatted_date = date_time.strftime('%Y-%m-%d %H:%M:%S')
            save_to_database(cursor, interface_id, data, int(timestamp))

        conn.commit()
        print(f"Data has been saved at {formatted_date} to the database.")
        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        time.sleep(60)
