function main(item) {
    // 初始化默认代理（可留空，靠规则匹配；也可保留一个通用代理）
    let proxyIp = "";
    let proxyPort = "";

    let playUrl = "";
    if (item && item.url) {
        const inputUrl = item.url;
        const idIndex = inputUrl.indexOf("?id=");
        if (idIndex !== -1) {
            playUrl = inputUrl.substring(idIndex + 4);
            playUrl = playUrl.split('&$')[0];
            try {
                playUrl = decodeURIComponent(playUrl);
            } catch (e) {}
        }
    }

    // ========== 所有域名的代理规则，统一简洁写法 ==========
    if (playUrl.includes("ott.mobaibox.com") || playUrl.includes("new.address.com")) {
        proxyIp = "223.111.182.16";
        proxyPort = "19009";
    } else if (playUrl.includes("hwltc.tv.cdn.zj.chinamobile.com")){
        // 给这个域名配专属代理，写法和其他域名一致
        proxyIp = "47.110.252.246";
        proxyPort = "60020";
    } else if (playUrl.includes("gslbserv.itv.cmvideo.cn")){
        // 给这个域名配专属代理，写法和其他域名一致
        proxyIp = "120.226.12.155";
        proxyPort = "31167";
    } else if (playUrl.includes("ottrrs.hl.chinamobile.com")){
        // 给这个域名配专属代理，写法和其他域名一致
        proxyIp = "111.42.183.124";
        proxyPort = "2022";
    }else if (playUrl.includes("ott.fj.chinamobile.com")){
        // 给这个域名配专属代理，写法和其他域名一致
        proxyIp = "112.5.173.148";
        proxyPort = "63180";
    }else if (playUrl.includes("tvgslb.hn.chinamobile.com")){
        // 给这个域名配专属代理，写法和其他域名一致
        proxyIp = "120.226.12.155";
        proxyPort = "31167";
    }else if (playUrl.includes("live2.rxip.sc96655.com")){
        // 给这个域名配专属代理，写法和其他域名一致
        proxyIp = "36.7.84.196";
        proxyPort = "9675";
    }

    ku9.setProxy(proxyIp, proxyPort);
    return {
        url: playUrl,
        player: 3
    };
}
