#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world_file_name = 'Example_PCD.sdf'
    robot_gazebo_share = get_package_share_directory('robot_gazebo')
    world = os.path.join(robot_gazebo_share, 'worlds', world_file_name)
    model_path = os.path.join(robot_gazebo_share, 'models')
    launch_file_dir = os.path.join(
        robot_gazebo_share, 'launch')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')

    existing_model_path = os.environ.get('GAZEBO_MODEL_PATH', '')
    gazebo_model_path = model_path if not existing_model_path else model_path + os.pathsep + existing_model_path

    return LaunchDescription([
        SetEnvironmentVariable('GAZEBO_MODEL_PATH', gazebo_model_path),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
            ),
            launch_arguments={'world': world}.items(),
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')
            ),
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [launch_file_dir, '/robot_state_publisher.launch.py']),
            launch_arguments={'use_sim_time': use_sim_time}.items(),
        ),
    ])
