Placeholder for the optional TwinSight `robot_adapter` package.

The Dockerfile copies this folder to `src/robot_adapter` when no `robot_adapter`
build context is supplied, so the image builds standalone. `COLCON_IGNORE`
keeps colcon from treating it as a package.

To build the image with the real robot_adapter, see
`docker/docker-compose.robot-adapter.yaml` and the README section
"Optional: running with the TwinSight robot_adapter".
