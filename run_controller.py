
from os_ken import cfg
from os_ken.base import app_manager


def main():
    cfg.CONF(args=[], project="os_ken")

    print("OS-Ken SDN controller starting...", flush=True)

    app_manager.AppManager.run_apps([
    "os_ken.controller.ofp_handler",
    "controller"
    ])


if __name__ == "__main__":
    main()
