package ru.rpo.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

private val Navy=Color(0xFF073C77); private val Blue=Color(0xFF0D63E6); private val Bg=Color(0xFFF4F7FB); private val Green=Color(0xFF1B9E50); private val Red=Color(0xFFD73535)

enum class Tab { FORM, HISTORY, HELP }

@Composable fun RpoApp(vm:RpoViewModel= viewModel()){
    val state by vm.state.collectAsState(); val history by vm.history.collectAsState(); var tab by remember{mutableStateOf(Tab.FORM)}
    LaunchedEffect(tab){if(tab==Tab.HISTORY)vm.loadHistory()}
    MaterialTheme(colorScheme=lightColorScheme(primary=Blue,background=Bg,error=Red)){
        Scaffold(containerColor=Bg,bottomBar={NavigationBar(containerColor=Color.White){
            NavigationBarItem(tab==Tab.FORM,{tab=Tab.FORM},{Icon(Icons.Default.Assignment,"Форма")},label={Text("Форма")})
            NavigationBarItem(tab==Tab.HISTORY,{tab=Tab.HISTORY},{Icon(Icons.Default.History,"История")},label={Text("История")})
            NavigationBarItem(tab==Tab.HELP,{tab=Tab.HELP},{Icon(Icons.Default.HelpOutline,"Справка")},label={Text("Справка")})
        }}){pad->Column(Modifier.padding(pad).fillMaxSize()){
            Header(); when(tab){Tab.FORM->FormScreen(state,vm);Tab.HISTORY->HistoryScreen(history);Tab.HELP->HelpScreen()}
        }}
    }
}

@Composable private fun Header(){Box(Modifier.fillMaxWidth().background(Navy).padding(18.dp)){Row(verticalAlignment=Alignment.CenterVertically){Icon(Icons.Default.Security,null,tint=Color.White,modifier=Modifier.size(38.dp));Spacer(Modifier.width(12.dp));Column{Text("РПО Мобайл",color=Color.White,fontSize=25.sp,fontWeight=FontWeight.Bold);Text("Передача этапов работ",color=Color.White.copy(alpha=.82f),fontSize=13.sp)};Spacer(Modifier.weight(1f));Surface(color=Color(0xFF14734C),shape=RoundedCornerShape(50)){Text("● Без входа — релиз 1",Modifier.padding(horizontal=10.dp,vertical=7.dp),color=Color.White,fontSize=11.sp)}}}}

@Composable private fun FormScreen(s:FormState,vm:RpoViewModel){Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),verticalArrangement=Arrangement.spacedBy(13.dp)){
    if(s.message!=null){Surface(color=if(s.success)Color(0xFFE9F8EE) else Color(0xFFFFF2E2),shape=RoundedCornerShape(12.dp)){Row(Modifier.padding(13.dp),verticalAlignment=Alignment.CenterVertically){Icon(if(s.success)Icons.Default.CheckCircle else Icons.Default.Warning,null,tint=if(s.success)Green else Color(0xFFE98B00));Spacer(Modifier.width(9.dp));Text(s.message,fontWeight=FontWeight.SemiBold)}}}
    Field("ФИО работника",s.workerName,{vm.updateWorker(it)},"Например: Иванов И.И.",s.errors["worker"])
    Field("Номер наряда-допуска",s.permitNumber,{vm.updatePermit(it)},"Введите вручную, например СН-038364",s.errors["permit"])
    StagePicker(s.stage,vm::updateStage)
    if(s.stage.kind==StageKind.DATETIME){Text("Дата и время события",fontWeight=FontWeight.SemiBold);Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){Box(Modifier.weight(1f)){Field(null,s.date,vm::updateDate,"ДД.ММ.ГГГГ",s.errors["datetime"])};Box(Modifier.weight(.7f)){Field(null,s.time,vm::updateTime,"ЧЧ:ММ",null)};OutlinedButton(vm::now,modifier=Modifier.height(56.dp)){Icon(Icons.Default.Schedule,null);Spacer(Modifier.width(4.dp));Text("Сейчас")}}}
    else Field(if(s.stage.key=="BE")"Данные о продлении" else "Статус закрытия ЭНД",s.customValue,vm::updateCustom,"Введите значение",s.errors["value"])
    Field("Комментарий${if(s.stage.commentRequired)" / причина остановки" else " (необязательно)"}",s.comment,vm::updateComment,"Введите комментарий",s.errors["comment"],singleLine=false)
    Button(onClick=vm::send,enabled=!s.sending,modifier=Modifier.fillMaxWidth().height(58.dp),shape=RoundedCornerShape(12.dp)){if(s.sending)CircularProgressIndicator(Modifier.size(22.dp),strokeWidth=2.dp,color=Color.White) else Icon(Icons.Default.Send,null);Spacer(Modifier.width(8.dp));Text(if(s.sending)"Отправка..." else "Отправить на сервер",fontWeight=FontWeight.Bold)}
    Surface(color=Color(0xFFF0F8F3),shape=RoundedCornerShape(12.dp),modifier=Modifier.fillMaxWidth()){Column(Modifier.padding(12.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){CheckLine(s.workerName.trim().length>=3,"ФИО указано");CheckLine(s.permitNumber.trim().length>=3,"Номер НД заполнен");CheckLine(s.errors["datetime"]==null,"Дата и время корректны")}}
    Spacer(Modifier.height(10.dp))
}}

@Composable private fun Field(label:String?,value:String,onValue:(String)->Unit,placeholder:String,error:String?,singleLine:Boolean=true){Column(verticalArrangement=Arrangement.spacedBy(5.dp)){if(label!=null)Text(label,fontWeight=FontWeight.SemiBold,fontSize=14.sp);OutlinedTextField(value,onValueChange=onValue,modifier=Modifier.fillMaxWidth(),placeholder={Text(placeholder)},singleLine=singleLine,isError=error!=null,shape=RoundedCornerShape(11.dp),minLines=if(singleLine)1 else 3,maxLines=if(singleLine)1 else 5);if(error!=null)Text(error,color=Red,fontSize=12.sp)}}

@Composable private fun StagePicker(selected:Stage,onSelect:(Stage)->Unit){var open by remember{mutableStateOf(false)};Column(verticalArrangement=Arrangement.spacedBy(5.dp)){Text("Этап работ",fontWeight=FontWeight.SemiBold,fontSize=14.sp);Box{OutlinedCard(Modifier.fillMaxWidth().clickable{open=true},shape=RoundedCornerShape(11.dp)){Row(Modifier.padding(16.dp),verticalAlignment=Alignment.CenterVertically){Icon(Icons.Default.Flag,null,tint=Blue);Spacer(Modifier.width(9.dp));Text(selected.title,Modifier.weight(1f));Icon(Icons.Default.KeyboardArrowDown,null)}};DropdownMenu(open,{open=false}){stages.forEach{DropdownMenuItem({Text("${it.key} · ${it.title}")},{onSelect(it);open=false})}}}}}
@Composable private fun CheckLine(ok:Boolean,text:String){Row(verticalAlignment=Alignment.CenterVertically){Icon(if(ok)Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked,null,tint=if(ok)Green else Color.Gray,modifier=Modifier.size(19.dp));Spacer(Modifier.width(7.dp));Text(text,fontSize=13.sp)}}

@Composable private fun HistoryScreen(items:List<ru.rpo.mobile.data.EventResponse>){Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){Text("История этого устройства",fontSize=22.sp,fontWeight=FontWeight.Bold);Text("Последние передачи на сервер",color=Color.Gray);if(items.isEmpty())Text("Переданных записей пока нет.",Modifier.padding(top=24.dp),color=Color.Gray);items.forEach{e->ElevatedCard(Modifier.fillMaxWidth()){Column(Modifier.padding(14.dp)){Row{Text(e.permit_number,fontWeight=FontWeight.Bold,color=Navy);Spacer(Modifier.weight(1f));Text(e.field_key,color=Blue,fontWeight=FontWeight.Bold)};Text(e.stage_label,fontWeight=FontWeight.SemiBold);Text(e.field_value,color=Color.DarkGray);if(e.comment.isNotBlank())Text(e.comment,color=Color.Gray,fontSize=12.sp);Text(if(e.exported_at==null)"На сервере · не выгружено" else "Выгружено оператором",color=if(e.exported_at==null)Color(0xFFE58A00) else Green,fontSize=12.sp,modifier=Modifier.padding(top=7.dp))}}}}}
@Composable private fun HelpScreen(){Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){Text("Справка",fontSize=22.sp,fontWeight=FontWeight.Bold);Text("1. Укажите ФИО — приложение запомнит его на этом устройстве.\n\n2. Введите номер НД вручную.\n\n3. Выберите этап.\n\n4. Заполните дату/время или нажмите «Сейчас».\n\n5. Для остановки обязательно укажите причину.\n\n6. Нажмите «Отправить на сервер».\n\nСервер дополнительно проверяет последовательность дат и не принимает явные ошибки.")}}
