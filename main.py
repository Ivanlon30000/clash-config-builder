import argparse
import os
from glob import glob
from typing import *

import yaml
from loguru import logger as log
from requests import get


class ClashConfig:
    sub_url: str
    config: Dict[str, Any]
    
    def __init__(self, name:str, sub_url:str, region_keywords:Dict[str, Any]) -> None:
        self.sub_url = sub_url
        self.name = name
        self.region_keywords = region_keywords
        self.config = {}
        
    def update_proxies(self):
        log.info("更新节点：{} {}", self.name, self.sub_url)
        resp = get(self.sub_url)
        proxies = yaml.safe_load(resp.content)
        proxies = proxies["proxies"]
        log.info("共{}个节点", len(proxies))
        for region, keywords in self.region_keywords.items():
            with open(f"proxies/{self.name}_{region}.yaml", "w", encoding="utf8") as fp:
                yaml.safe_dump({
                    "proxies": [proxy for proxy in proxies if any(keyword.lower() in proxy["name"].lower() for keyword in keywords)]
                }, fp, allow_unicode=True)
    
    def build(self, file:str) -> "ClashConfig":
        with open(file, "r", encoding="utf-8") as fp:
            self.config.update(yaml.safe_load(fp))
        return self
    
    def build_base(self) -> "ClashConfig":
        return self.build("base.yaml")
    
    def build_proxy(self) -> "ClashConfig":
        proxy_providers = [{
            region: {
                "type": "file",
                "path": f"./proxies/{self.name}_{region}.yaml",
            }
        } for region in self.region_keywords]
        
        proxy_groups = [{
            "name": region,
            "type": "url-test",
            "use": [region],
            "url": "http://www.gstatic.com/generate_204"
        } for region in self.region_keywords]
        
        self.config.update({
            "proxy-providers": proxy_providers,
            "proxy-groups": proxy_groups
        })
        
        return self
    
    def build_rules(self, 
                   mode:Literal["whitelist", "blacklist", ""]="whitelist", 
                   user_defined:List[str]|str=["*"]) -> "ClashConfig":
        # rule-providers
        with open("rule-providers.yaml", "r", encoding="utf8") as fp:
            rule_providers = yaml.safe_load(fp)
            self.config.update(rule_providers)
        
        final_rules = []
        
        # 自定义rule
        if isinstance(user_defined, str):
            user_defined = [user_defined]
        root = "./rules/user-defined"
        for glob_expr in user_defined:
            for filename in glob(glob_expr, root_dir=root):
                log.info("加载自定义规则{} ...", filename)
                with open(os.path.join(root, filename), "r", encoding="utf8") as fp:
                    rule = yaml.safe_load(fp)
                    rule = rule.get("rules", None) or []
                log.info("加载自定义规则{} {}条", filename, len(rule))
                final_rules.extend(rule)
        log.info("共加载自定义规则{}条", len(final_rules))
        
        # 黑白名单
        if mode:
            with open(f"rules/{mode}.yaml", "r", encoding="utf8") as fp:
                rule = yaml.safe_load(fp)
                rule = rule.get("rules", None) or []
                final_rules.extend(rule)
        self.config["rules"] = final_rules
        log.info("共计{}条规则", len(final_rules))

        return self
    
    def build_all(self) -> "ClashConfig":
        self.update_proxies()
        self.build_base()
        self.build_proxy()
        self.build_rules()
        return self
    
    def dump(self, path:str="config.yaml") -> None:
        with open(path, "w", encoding="utf8") as fp:
            yaml.safe_dump(self.config, fp, indent=2, allow_unicode=True, sort_keys=False)
    

def main(config_path):
    import json
    with open(config_path, "r", encoding="utf8") as fp:
        config = json.load(fp)
    ClashConfig(
        name=config["name"],
        sub_url=config["sub_url"],
        region_keywords=config["region_keywords"]
    ).build_all().dump(config["target_path"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", default="builder-config.json")
    args = parser.parse_args()
    main(args.config_path)