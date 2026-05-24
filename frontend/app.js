/* ================= 字数统计功能 ================= */

/*获取输入框*/
const userText=document.getElementById("userText");

/**找到：id="userText"这个输入框。以后JS才能操作它 **/

/*获取字数统计区域*/
const counter=document.querySelector(".counter");

/*监听输入事件*/
/**input作用：监听用户在输入**/
userText.addEventListener("input",function(){
    let currentLength=userText.value.length;
    /*获取当前输入内容长度 */


    /*更新页面文字*/
    counter.textContent=currentLength+"/1000";}
)

/* ================= 上传文件功能 ================= */
/*获取上传按钮*/ 
const uploadBtn=document.getElementById("uploadBtn");

/*获取文件输入框*/ 
const uploadInput=document.getElementById("uploadInput"); 

/*获取显示区域*/ 
const fileInfo=document.getElementById("fileInfo");

/** 点击按钮触发文件选择*/
uploadBtn.addEventListener("click",function(){
    uploadInput.click();
}
);

/*监听文件变化*/ 
uploadInput.addEventListener("change",function(){
    /*获取第一个文件*/ 
    const file=uploadInput.files[0];

    if(!file){
        return;
    }

    let fileSize=file.size/1024/1024;

    let allowedTypes=[
        "image/jpeg",

        "image/png",

        "image/jpg",

        "video/mp4",

        "video/quicktime",

        "video/x-msvideo"
    ];
    /*格式检查*/ 
    if(!allowedTypes.includes(file.type)){
    alert("仅支持图片或视频格式");  
    return;
}

    /* 大小检查*/
    if(fileSize>50){
    alert("文件不能超过50MB");
    return;
} 

    /* 显示上传结果*/
    fileInfo.textContent="已上传"+file.name;
});

/* ================= 提交按钮功能并且更新界面（前后端联调） ================= */

/*获取提交按钮*/
const submitBtn=document.getElementById("submitBtn");

/*获取结果显示区域*/
const resultContent=document.getElementById("resultContent");


/*监听提交*/
submitBtn.addEventListener(

    "click",

    async function(){

        /*获取文本内容*/
        let content=

        userText.value.trim();



        /*空输入检查*/
        if(content===""){

            alert("请输入问题描述");

            return;

        }



        /*获取上传文件*/
        const file=

        uploadInput.files[0];



        /*创建FormData*/
        let formData=

        new FormData();



        /*字段名必须和FastAPI一致*/
        formData.append(

            "text",

            content

        );



        /*有文件再上传*/
        if(file){

            formData.append(

                "image",

                file

            );

        }

        try{
            /*请求后端*/
            const response=
            await fetch(
                "http://localhost:8000/process",
                {
                    method:"POST",
                    body:formData
                }
            );
            /*解析JSON*/
            const data=
            await response.json();/*等待并解析 HTTP 响应体，将其从 JSON 格式转换为 JavaScript 对象或数组。*/
            console.log(data);/*在控制台打印出 data 的内容，方便调试或查看返回的数据结构。*/
            
            /*更新界面*/
            resultContent.innerHTML=`
                <div class="robot-icon">
                    🤖
                </div>
                <h3>
                    分析完成
                </h3>
                <p>
                    AI 已生成识别结果
                </p>
                <div class="feature-row">
                    <div class="feature-card">
                        🏷
                        <span>
                            <!-- 问题分类-->
                            ${data.extracted_data.issue_category}
                        </span>
                    </div>
                    <div class="feature-card">
                        ⚠
                        <span>
                            <!-- 紧急程度 -->
                            ${data.extracted_data.urgency_level}
                        </span>
                    </div>
                    <div class="feature-card">
                        💬
                        <span>
                            <!-- 建议 -->
                            ${data.agent_business_assessment}
                        </span>
                    </div>
                    <div class="feature-card">
                        💡
                        <span>
                            <!-- 路由决策 -->
                            ${data.routing_decision}
                        </span>
                    <div>
                    <div class="feature-card">
                        🛡
                        <span>
                            <!-- 订单id-->
                            ${data.ticket_id}
                        </span>
                    <div>
                <div>
                `;
        }

        catch(error){
            console.error(error);
            alert(
                "连接后端失败"
            );
        }
    }
);

/* ================= 历史工单 ================= */

/*获取历史工单区域*/
const historyContainer=document.getElementById("historyContainer");

async function loadHistory(){
    try{
        const response=await fetch(
            "http://localhost:8000/history"
        );
        const data=await response.json();

        renderHistory(data);
    }

    catch(error){
        console.error(error);
    }
}

/*渲染历史记录*/
function renderHistory(data) {
    if(data.length===0){
        return;
    }
    let html="";

    data.forEach(
        function(ticket){
            html+=`
            <div class="history-card">
                <h4>
                    工单id:${ticket.ticket_id}
                </h4>
                <p>
                    ${ticket.issue_category}
                </p>
                <p>
                    ${ticket.created_at}
                </p>
            </div>
            `; 
        }
    );
    historyContainer.innerHTML=html;
}