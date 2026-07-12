# `yn_robot` — Robot Specification

A 4-wheeled, front-steered rover (Ackermann-style) built in Gazebo to traverse an
IFC-derived world and generate point clouds via LIO-SAM (ROS 2).

## Kinematic tree

```
base_footprint
└─ base_link                          (fixed, at origin)
   ├─ front_right_steering_link       (revolute)  → front_right_wheel_link (continuous)
   ├─ front_left_steering_link        (revolute)  → front_left_wheel_link  (continuous)
   ├─ right_wheel_link                (continuous, driven)
   ├─ left_wheel_link                 (continuous, driven)
   ├─ velodyne_base_link → velodyne   (fixed, inverted)
   └─ imu_link                        (fixed, inverted)
```

## Chassis

| Property | Value |
|---|---|
| Base mass | 10 kg |
| Inertia | ixx 0.237, iyy 0.207, izz 0.351, iyz −0.035 |
| Frames | `base_footprint` → `base_link` |

## Drivetrain & steering

| Element | Joint type | Mount `xyz` / `rpy` | Mass | Limits |
|---|---|---|---|---|
| Front-R steering | revolute | −0.35, −0.15, 0 / π 0 0 | 0.15 kg | ±2.1 rad (~±120°), eff 5, vel 6.28 |
| Front-L steering | revolute | −0.35, +0.15, 0 / π 0 0 | 0.15 kg | ±2.1 rad, eff 5, vel 6.28 |
| Front-R wheel | continuous | on steering link | 0.137 kg | eff 1.5, vel 20 |
| Front-L wheel | continuous | on steering link | 0.137 kg | eff 1.5, vel 20 |
| Rear-R wheel | continuous (driven) | +0.275, −0.17, 0.1 | 1.75 kg | via transmission |
| Rear-L wheel | continuous (driven) | +0.275, +0.17, 0.1 | 1.75 kg | via transmission |

- **Wheelbase** ≈ 0.625 m (front x −0.35 → rear x +0.275); **track** ≈ 0.30–0.34 m
- Front wheels are **steered but not driven**; rear wheels are **driven** (rear-wheel transmission)

## LiDAR — Velodyne VLP-16 (custom-tuned)

| Property | Value |
|---|---|
| Channels | 16 |
| Update rate | 10 Hz |
| Horizontal samples | 440 (matches LIO-SAM `Horizon_SCAN`) |
| **Vertical FOV** | **−15° to +45°** — real VLP-16 spec is ±15°; widened intentionally for indoor coverage |
| Range | 0.9–130 m (sim) / 0.2–100 m used in LIO-SAM |
| Gaussian noise | 0.008 m |
| Mount | `xyz 0 0 −0.4`, `rpy 0 π 0` → mounted **inverted**, below `base_link` |
| Mass | 0.83 kg |
| Topic | `/points_raw` → LIO-SAM `pointCloudTopic: points_raw` |

## IMU

| Property | Value |
|---|---|
| Update rate | 200 Hz |
| Mount | `xyz 0 0 −0.297`, `rpy 0 π 0` → **inverted** |
| Mass | 0.005 kg |
| Plugin | `libgazebo_ros_imu_sensor.so` (ROS 2) |
| Published topic | `/imu_plugin/out` (explicit `~/out` remap) |
| Frame | `base_link` |
| LIO-SAM noise | acc 3.99e-3, gyro 1.56e-3, accBias 6.44e-5, gyroBias 3.56e-5 |
| Gravity | 9.80511 |
| LiDAR↔IMU extrinsic | trans `[0, 0, −0.0103]`, identity rotation |

## SLAM — LIO-SAM

- Sensor: `velodyne`, `N_SCAN` 16, `Horizon_SCAN` 440, `downsampleRate` 1
- **Indoor** voxel tuning: surf 0.2, corner 0.1; edge/surf thresholds 1.0 / 0.1
- Loop closure **enabled** (1 Hz, search radius 15 m, ICP fitness 0.3)
- Keyframe adding: 1.0 m / 0.2 rad; near-2D constraints (`z_tollerance` 0.05, `rotation_tollerance` 0.20)
- PCD export **enabled** → `/TUM/Thesis/bim3dscenegraph/pc_models/`

## Topic wiring

| Topic | Producer | Consumer |
|---|---|---|
| `/points_raw` | VLP-16 Gazebo plugin | LIO-SAM (`pointCloudTopic`) |
| `/imu_plugin/out` | IMU Gazebo plugin | LIO-SAM (`imuTopic`), `robot_control.py` |
| `cmd_vel` | `robot_control.py` | Gazebo diff/steer controller |
| `joy` | joystick | `robot_control.py` |

## Source files

| Component | File |
|---|---|
| Top-level assembly | `src/robot_description/robot/robot.urdf.xacro` |
| Base | `src/robot_description/urdf/base/base.urdf.xacro` |
| Steering | `src/robot_description/urdf/suspension/suspension.urdf.xacro` |
| Front / rear wheels | `src/robot_description/urdf/{front_wheel,rear_wheel}/*.urdf.xacro` |
| IMU | `src/robot_description/urdf/IMU/IMU.{urdf,gazebo}.xacro` |
| VLP-16 | `src/velodyne_simulator/velodyne_description/urdf/VLP-16.urdf.xacro` |
| LIO-SAM config | `src/LIO-SAM-ros2/config/params.yaml` |
