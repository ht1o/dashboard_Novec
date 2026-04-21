import pandas as pd
import numpy as np
import random

def generate_infrastructure(daterange_hours, start_date):
    """
    Génère les 6 KPIs Infrastructure IT + métriques détaillées.
    
    Patterns simulés :
    - Cycle jour/nuit pour CPU/RAM
    - Dégradation lente du disque (trend linéaire +0.15%/jour)
    - Anomalies multivariées (CPU+Latence+Backup) pour Isolation Forest
    - MTBF et MTTR calculés dynamiquement
    
    Le DataFrame retourné contient aussi une colonne 'Is_Anomaly' 
    pour servir de signal aux générateurs ITSM et Applications.
    """
    data = []
    servers = ['SRV-ERP-01', 'SRV-DB-01', 'SRV-WEB-PME']
    
    # État de tracking par serveur pour MTBF/MTTR
    last_failure = {srv: None for srv in servers}
    hours_since_failure = {srv: 0 for srv in servers}
    
    for date in daterange_hours:
        hour = date.hour
        is_weekend = date.weekday() >= 5
        day_index = (date - start_date).days
        
        for srv in servers:
            is_working_hour = 8 <= hour <= 18 and not is_weekend
            is_anomaly = False
            
            # --- Cycle jour/nuit CPU/RAM ---
            base_cpu = np.random.normal(65, 10) if is_working_hour else np.random.normal(30, 5)
            base_ram = np.random.normal(70, 5) if is_working_hour else np.random.normal(45, 5)
            base_latency = np.random.normal(15, 3)
            backup_status = int(np.random.choice([1, 1, 1, 1, 0])) if hour == 2 else 1
            
            # --- Dégradation lente disque (pour Prophet) ---
            disk_usage_trend = 45 + (day_index * 0.15)
            
            # --- Injection anomalie multivariée (pour Isolation Forest) ---
            if srv == 'SRV-ERP-01' and is_working_hour and random.random() < 0.005:
                base_cpu = np.random.normal(98, 1)
                base_latency = np.random.normal(250, 50)
                base_ram = np.random.normal(95, 2)
                backup_status = 0
                is_anomaly = True
            
            # Anomalies ponctuelles sur les autres serveurs aussi (plus rare)
            if srv != 'SRV-ERP-01' and random.random() < 0.002:
                base_cpu = np.random.normal(95, 2)
                base_latency = np.random.normal(180, 30)
                is_anomaly = True
            
            cpu = min(100.0, max(0.0, float(base_cpu)))
            ram = min(100.0, max(0.0, float(base_ram)))
            disk = min(100.0, max(0.0, float(disk_usage_trend + np.random.normal(0, 1))))
            latency = max(0.0, round(float(base_latency), 2))
            uptime = 0 if cpu > 98.0 else 1
            
            # --- MTBF (Mean Time Between Failures) ---
            if uptime == 0:
                mtbf = float(hours_since_failure[srv])
                hours_since_failure[srv] = 0
                last_failure[srv] = date
            else:
                hours_since_failure[srv] += 1
                mtbf = float(hours_since_failure[srv])
            
            # --- MTTR Infra (temps de rétablissement) ---
            mttr_infra = round(float(np.random.normal(1.5, 0.5)), 2) if uptime == 0 else 0.0
            
            # --- Backup Coverage (agrégé journalier simulé) ---
            backup_coverage = 100.0 if backup_status == 1 else round(float(np.random.uniform(70, 90)), 2)
            
            data.append({
                'Timestamp': date.strftime('%Y-%m-%d %H:%M:%S'),
                'ServerName': srv,
                'CPU_Usage_Pct': round(cpu, 2),
                'RAM_Usage_Pct': round(ram, 2),
                'Disk_Usage_Pct': round(disk, 2),
                'Network_Latency_ms': latency,
                'Backup_Success': backup_status,
                'Backup_Coverage_Pct': backup_coverage,
                'Uptime_Status': uptime,
                'MTBF_Hours': round(mtbf, 2),
                'MTTR_Infra_Hours': mttr_infra,
                'Is_Anomaly': int(is_anomaly)
            })
    return pd.DataFrame(data)
