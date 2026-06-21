"""Tracked exchange-traded QDII fund configuration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EtfConfig:
    """Configuration for a tracked exchange-traded fund."""

    code: str
    name: str
    short_name: str
    market: str
    eastmoney_secid: str
    tracking_index: str
    tracking_index_name: str


TRACKED_ETFS: dict[str, EtfConfig] = {
    "159509": EtfConfig(
        code="159509",
        name="纳指科技ETF景顺 (159509)",
        short_name="纳指科技ETF景顺",
        market="sz",
        eastmoney_secid="0.159509",
        tracking_index="NASDAQ_TECH",
        tracking_index_name="纳斯达克科技市值加权指数",
    ),
    "513100": EtfConfig(
        code="513100",
        name="纳指ETF国泰 (513100)",
        short_name="纳指ETF国泰",
        market="sh",
        eastmoney_secid="1.513100",
        tracking_index="NASDAQ100",
        tracking_index_name="纳斯达克100指数",
    ),
    "513300": EtfConfig(
        code="513300",
        name="纳斯达克ETF华夏 (513300)",
        short_name="纳斯达克ETF华夏",
        market="sh",
        eastmoney_secid="1.513300",
        tracking_index="NASDAQ100",
        tracking_index_name="纳斯达克100指数",
    ),
    "159501": EtfConfig(
        code="159501",
        name="纳指ETF嘉实 (159501)",
        short_name="纳指ETF嘉实",
        market="sz",
        eastmoney_secid="0.159501",
        tracking_index="NASDAQ100",
        tracking_index_name="纳斯达克100指数",
    ),
    "159696": EtfConfig(
        code="159696",
        name="纳指ETF易方达 (159696)",
        short_name="纳指ETF易方达",
        market="sz",
        eastmoney_secid="0.159696",
        tracking_index="NASDAQ100",
        tracking_index_name="纳斯达克100指数",
    ),
    "159659": EtfConfig(
        code="159659",
        name="纳斯达克100ETF招商 (159659)",
        short_name="纳斯达克100ETF招商",
        market="sz",
        eastmoney_secid="0.159659",
        tracking_index="NASDAQ100",
        tracking_index_name="纳斯达克100指数",
    ),
    "159941": EtfConfig(
        code="159941",
        name="纳指ETF广发 (159941)",
        short_name="纳指ETF广发",
        market="sz",
        eastmoney_secid="0.159941",
        tracking_index="NASDAQ100",
        tracking_index_name="纳斯达克100指数",
    ),
    "513500": EtfConfig(
        code="513500",
        name="标普500ETF博时 (513500)",
        short_name="标普500ETF博时",
        market="sh",
        eastmoney_secid="1.513500",
        tracking_index="SP500",
        tracking_index_name="标普500指数",
    ),
    "513650": EtfConfig(
        code="513650",
        name="标普500ETF南方 (513650)",
        short_name="标普500ETF南方",
        market="sh",
        eastmoney_secid="1.513650",
        tracking_index="SP500",
        tracking_index_name="标普500指数",
    ),
    "513310": EtfConfig(
        code="513310",
        name="中韩半导体ETF华泰柏瑞 (513310)",
        short_name="中韩半导体ETF华泰柏瑞",
        market="sh",
        eastmoney_secid="1.513310",
        tracking_index="CSI_KR_SEMI",
        tracking_index_name="中证韩交所中韩半导体指数",
    ),
}
