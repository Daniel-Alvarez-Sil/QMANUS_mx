#!/usr/bin/env python3
"""
insert_tenant_b_data.py - Insert test data for Tenant B to demonstrate isolation

This script inserts additional agent sessions and tool calls specifically for Tenant B
to prove that tenant isolation works correctly.
"""

import asyncio
import mysql.connector
from datetime import datetime, timedelta
import json
import random

# Database configuration
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 4000,
    'user': 'root',
    'password': '',
    'database': 'agentnexus',
    'charset': 'utf8mb4'
}

TENANT_B_ID = 'ent-B'

# Sample data for Tenant B
AGENT_TYPES = ['research', 'codegen', 'data', 'web']
TOOL_NAMES = ['web_search', 'code_exec', 'db_query', 'file_read', 'api_call']

def generate_session_data():
    """Generate realistic session data for Tenant B"""
    sessions = []
    current_time = datetime.now()
    
    # Generate 15 new sessions for Tenant B over the last 3 days
    for i in range(15):
        session_time = current_time - timedelta(hours=i*4)
        agent_type = random.choice(AGENT_TYPES)
        status = random.choices(['completed', 'failed', 'running'], weights=[0.7, 0.2, 0.1])[0]
        
        session = {
            'session_id': f'sess-b-demo-{i+1:03d}',
            'tenant_id': TENANT_B_ID,
            'agent_type': agent_type,
            'status': status,
            'task_plan': json.dumps({
                'steps': [f'step_{j}' for j in range(1, 4)],
                'priority': random.choice(['high', 'medium', 'low'])
            }),
            'context': json.dumps({
                'user_id': f'user-b-{i+1}',
                'department': random.choice(['engineering', 'research', 'data'])
            }),
            'created_at': session_time,
            'updated_at': session_time + timedelta(minutes=random.randint(30, 120))
        }
        sessions.append(session)
    
    return sessions

def generate_tool_calls(sessions):
    """Generate tool calls for the sessions"""
    tool_calls = []
    
    for session in sessions:
        # Generate 3-8 tool calls per session
        num_calls = random.randint(3, 8)
        
        for i in range(num_calls):
            call_time = session['created_at'] + timedelta(minutes=i*15)
            tool_name = random.choice(TOOL_NAMES)
            status = random.choices(['success', 'failed', 'timeout'], weights=[0.8, 0.15, 0.05])[0]
            
            tool_call = {
                'call_id': f'call-b-{session["session_id"].split("-")[-1]}-{i+1:02d}',
                'session_id': session['session_id'],
                'tenant_id': TENANT_B_ID,
                'tool_name': tool_name,
                'input_params': json.dumps({
                    'query': f'demo query {i+1}',
                    'timeout': random.randint(10, 60)
                }),
                'output_result': json.dumps({
                    'status': status,
                    'data': f'result_{i+1}' if status == 'success' else None
                }),
                'status': status,
                'latency_ms': random.randint(50, 2000) if status == 'success' else random.randint(5000, 15000),
                'called_at': call_time
            }
            tool_calls.append(tool_call)
    
    return tool_calls

async def insert_tenant_b_data():
    """Insert the generated data into the database"""
    
    print("🔐 Inserting Tenant B demo data to test isolation...")
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Generate data
        sessions = generate_session_data()
        tool_calls = generate_tool_calls(sessions)
        
        print(f"📊 Generated {len(sessions)} sessions and {len(tool_calls)} tool calls for Tenant B")
        
        # Insert sessions
        session_query = """
        INSERT INTO agent_sessions 
        (session_id, tenant_id, agent_type, status, task_plan, context, created_at, updated_at)
        VALUES (%(session_id)s, %(tenant_id)s, %(agent_type)s, %(status)s, 
                %(task_plan)s, %(context)s, %(created_at)s, %(updated_at)s)
        """
        
        cursor.executemany(session_query, sessions)
        print(f"✅ Inserted {cursor.rowcount} sessions for Tenant B")
        
        # Insert tool calls
        tool_call_query = """
        INSERT INTO tool_call_history 
        (call_id, session_id, tenant_id, tool_name, input_params, output_result, 
         status, latency_ms, called_at)
        VALUES (%(call_id)s, %(session_id)s, %(tenant_id)s, %(tool_name)s,
                %(input_params)s, %(output_result)s, %(status)s, 
                %(latency_ms)s, %(called_at)s)
        """
        
        cursor.executemany(tool_call_query, tool_calls)
        print(f"✅ Inserted {cursor.rowcount} tool calls for Tenant B")
        
        # Commit transaction
        conn.commit()
        
        # Verify the data was inserted
        cursor.execute("SELECT COUNT(*) FROM agent_sessions WHERE tenant_id = %s", (TENANT_B_ID,))
        session_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tool_call_history WHERE tenant_id = %s", (TENANT_B_ID,))
        tool_count = cursor.fetchone()[0]
        
        print(f"\n📈 Tenant B now has:")
        print(f"   • {session_count} total sessions")
        print(f"   • {tool_count} total tool calls")
        
        # Show recent activity
        cursor.execute("""
        SELECT agent_type, status, created_at 
        FROM agent_sessions 
        WHERE tenant_id = %s 
        ORDER BY created_at DESC 
        LIMIT 5
        """, (TENANT_B_ID,))
        
        recent_sessions = cursor.fetchall()
        print(f"\n🕒 Recent Tenant B activity:")
        for session in recent_sessions:
            agent_type, status, created_at = session
            print(f"   • {agent_type} agent - {status} - {created_at}")
        
    except Exception as e:
        print(f"❌ Error inserting data: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()

def verify_isolation():
    """Verify that Tenant A and Tenant B data are properly isolated"""
    print("\n🔒 Verifying tenant isolation...")
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check Tenant A data
        cursor.execute("SELECT COUNT(*) FROM agent_sessions WHERE tenant_id = 'ent-A'")
        tenant_a_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tool_call_history WHERE tenant_id = 'ent-A'")
        tenant_a_tools = cursor.fetchone()[0]
        
        # Check Tenant B data
        cursor.execute("SELECT COUNT(*) FROM agent_sessions WHERE tenant_id = 'ent-B'")
        tenant_b_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tool_call_history WHERE tenant_id = 'ent-B'")
        tenant_b_tools = cursor.fetchone()[0]
        
        print(f"\n📊 Data Summary:")
        print(f"   Tenant A: {tenant_a_sessions} sessions, {tenant_a_tools} tool calls")
        print(f"   Tenant B: {tenant_b_sessions} sessions, {tenant_b_tools} tool calls")
        
        # Verify no cross-contamination
        cursor.execute("""
        SELECT COUNT(*) FROM agent_sessions 
        WHERE tenant_id != 'ent-A' AND tenant_id != 'ent-B'
        """)
        other_sessions = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT COUNT(*) FROM tool_call_history 
        WHERE tenant_id != 'ent-A' AND tenant_id != 'ent-B'
        """)
        other_tools = cursor.fetchone()[0]
        
        if other_sessions == 0 and other_tools == 0:
            print("✅ Tenant isolation verified - no cross-contamination detected")
        else:
            print(f"⚠️  Found {other_sessions} sessions and {other_tools} tools from other tenants")
        
    except Exception as e:
        print(f"❌ Error verifying isolation: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    print("🚀 Starting Tenant B data insertion for isolation demo...")
    asyncio.run(insert_tenant_b_data())
    verify_isolation()
    print("\n✨ Demo data insertion complete!")
    print("\n📝 Next steps:")
    print("1. Open the dashboard for Tenant A (enterprise-A)")
    print("2. Verify you only see Tenant A data")
    print("3. Try Tenant B credentials to see Tenant B data")
    print("4. Confirm isolation is working correctly")
