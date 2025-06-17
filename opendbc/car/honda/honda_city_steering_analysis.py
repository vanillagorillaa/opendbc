#!/usr/bin/env python3
"""
Honda City Steering Vibration Analysis Tool
"""

import os
import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# Add openpilot tools to path
sys.path.append('/data/openpilot')
sys.path.append('/data/openpilot/tools/lib')

from tools.lib.logreader import LogReader

def analyze_log(log_path):
    """Analyze a single log file"""
    print(f"Analyzing: {log_path}")
    
    try:
        lr = LogReader(str(log_path))
    except Exception as e:
        print(f"Error: {e}")
        return None
    
    # Data containers
    data = []
    
    for msg in lr:
        timestamp = msg.logMonoTime / 1e9
        
        if msg.which() == 'carState':
            cs = msg.carState
            data.append({
                'timestamp': timestamp,
                'speed_kph': cs.vEgo * 3.6,
                'steering_torque': cs.steeringTorque,
                'steering_angle': cs.steeringAngleDeg,
                'cruise_enabled': cs.cruiseState.enabled
            })
    
    if not data:
        return None
        
    df = pd.DataFrame(data)
    df['rel_time'] = df['timestamp'] - df['timestamp'].min()
    
    # Focus on vibration range
    vibration_data = df[(df['speed_kph'] >= 9) & (df['speed_kph'] <= 18)]
    
    if vibration_data.empty:
        print("No data in vibration range")
        return None
    
    # Analysis
    analysis = {
        'drive_time': len(vibration_data) / 100,  # seconds
        'avg_speed': vibration_data['speed_kph'].mean(),
        'torque_std': vibration_data['steering_torque'].std(),
        'torque_range': vibration_data['steering_torque'].max() - vibration_data['steering_torque'].min()
    }
    
    return {'df': df, 'analysis': analysis, 'vibration_data': vibration_data}

def create_plots(data, output_dir, drive_name):
    """Create diagnostic plots"""
    os.makedirs(output_dir, exist_ok=True)
    
    df = data['df']
    vibration_data = data['vibration_data']
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    # Speed plot
    axes[0].plot(df['rel_time'], df['speed_kph'], 'b-', alpha=0.7)
    axes[0].axhspan(9, 18, alpha=0.2, color='red', label='Vibration Range')
    axes[0].set_ylabel('Speed (km/h)')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f'Honda City Steering Analysis - {drive_name}')
    
    # Torque plot
    axes[1].plot(df['rel_time'], df['steering_torque'], 'g-', alpha=0.7)
    axes[1].set_ylabel('Steering Torque (Nm)')
    axes[1].set_xlabel('Time (seconds)')
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/analysis.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Scatter plot
    plt.figure(figsize=(10, 6))
    plt.scatter(df['speed_kph'], df['steering_torque'], alpha=0.6, s=1)
    plt.axvspan(9, 18, alpha=0.2, color='red', label='Vibration Range')
    plt.xlabel('Speed (km/h)')
    plt.ylabel('Steering Torque (Nm)')
    plt.title('Steering Torque vs Speed')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{output_dir}/scatter.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Plots saved to {output_dir}/")

def main():
    log_dir = Path('/data/media/0/realdata')
    
    # Find recent drives
    drives = sorted([d for d in log_dir.iterdir() if d.is_dir() and d.name != 'boot'], reverse=True)[:5]
    
    results = []
    
    for drive_path in drives:
        drive_name = drive_path.name
        rlog_path = drive_path / 'rlog.zst'
        
        if not rlog_path.exists():
            continue
            
        print(f"\n=== {drive_name} ===")
        
        data = analyze_log(rlog_path)
        if data is None:
            continue
            
        # Create plots
        output_dir = f"./steering_analysis/{drive_name}"
        create_plots(data, output_dir, drive_name)
        
        # Store results
        results.append({
            'drive': drive_name,
            'analysis': data['analysis']
        })
        
        # Print summary
        analysis = data['analysis']
        print(f"Time in range: {analysis['drive_time']:.1f}s")
        print(f"Avg speed: {analysis['avg_speed']:.1f} km/h")
        print(f"Torque std: {analysis['torque_std']:.3f} Nm")
        print(f"Torque range: {analysis['torque_range']:.3f} Nm")
    
    # Save results
    os.makedirs('./steering_analysis', exist_ok=True)
    with open('./steering_analysis/summary.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nAnalyzed {len(results)} drives")
    print("Results saved to ./steering_analysis/")

if __name__ == "__main__":
    main() 