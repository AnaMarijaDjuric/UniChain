import beaker
import pyteal as pt


# definisemo STATE nase aplikacije
class UniChainState:
    # player one
    # ovde cuvamo adresu studenta
    student = beaker.GlobalStateValue(
        stack_type=pt.TealType.bytes,
        descr="Student",
        default=pt.Bytes("No optedin student"),
    )
    # informacije o studentu
    # moracu da proverim da li mi je ovo uopste potrebno
    # nisam ovo do sad stavljala u app, provericu
    # ovde cuvamo mail studenta
    mail = beaker.GlobalStateValue(
        stack_type=pt.TealType.bytes,
        descr="Student's inf",
        default=pt.Bytes("No info"),
    )
    hash_pass = beaker.LocalStateValue(
        stack_type=pt.TealType.bytes,
        descr="Student's hashed password",
        default=pt.Bytes("No hash password"),
    )
    # player two
    library = beaker.GlobalStateValue(
        stack_type=pt.TealType.bytes,
        descr="Worker",
        default=pt.Bytes("No optedin worker"),
        #
    )

    # izabrana knjiga
    chosenBook = beaker.GlobalStateValue(
        stack_type=pt.TealType.bytes,
        descr="Student's chosen book",
        default=pt.Bytes("No chosen book"),
    )

    # uplata
    fee = beaker.GlobalStateValue(
        stack_type=pt.TealType.uint64, descr="Payment for books", default=pt.Int(0)
    )


app = beaker.Application("unichain_sc", state=UniChainState)


## create metoda
# u njoj samo pravimo app i inicijalizujemo globalne varijable na default vrednosti


@app.create(bare=True)
def create() -> pt.Expr:
    return app.initialize_global_state()




@app.opt_in(bare=True)
def opt_in() -> pt.Expr:

    return pt.Seq(
        pt.If(app.state.student.get() == pt.Bytes("No optedin student"))
        .Then(app.state.student.set(pt.Txn.sender()))
        .ElseIf(app.state.library.get() == pt.Bytes("No optedin worker"))
        .Then(app.state.library.set(pt.Txn.sender()))
        .Else(pt.Reject()),
        app.initialize_local_state(addr=pt.Txn.sender()),
    )

@app.external(authorize=beaker.Authorize.opted_in())
def student_login_and_ordering(
    mail: pt.abi.String,
    password: pt.abi.String,
    book: pt.abi.String,
    # *,
    # output: pt.abi.String
) -> pt.Expr:
    return pt.Seq(
        pt.Assert(
            pt.And(
                app.state.mail.get() == pt.Bytes("No info"),
                app.state.hash_pass[pt.Txn.sender()].get()
                == pt.Bytes("No hash password"),
                app.state.chosenBook.get() == pt.Bytes("No chosen book"),
            )
        ),
        app.state.mail.set(mail.get()),
        app.state.hash_pass[pt.Txn.sender()].set(pt.Sha256(password.get())),
        app.state.chosenBook.set(book.get()),
    )


@app.external(authorize=beaker.Authorize.opted_in())
def workers_acceptance() -> pt.Expr:
    chosen = pt.ScratchVar(pt.TealType.bytes)

    ordering_address = pt.ScratchVar(pt.TealType.bytes)
    return pt.Seq(
        pt.Assert(
            pt.And(
                app.state.chosenBook.get() != pt.Bytes("No chosen book"),
                app.state.mail.get() != pt.Bytes("No info"),
            )
        ),
        chosen.store(app.state.chosenBook.get()),
        ordering_address.store(app.state.mail.get()),
    )


# lower wager - to je onaj veliki bag na kraju testiranja koji iskace


@pt.Subroutine(pt.TealType.none)
def transfer_money(paying_fee: pt.Expr, acc_index: pt.Expr) -> pt.Expr:
    return pt.Seq(
        # priprema inner transaction za nas
        pt.InnerTxnBuilder.Begin(),
        pt.InnerTxnBuilder.SetFields(
            {
                pt.TxnField.type_enum: pt.TxnType.Payment,
                pt.TxnField.receiver: pt.Txn.accounts[acc_index],
                # pt.TxnField.receiver: acc_index,
                pt.TxnField.amount: paying_fee - pt.Txn.fee,
            }
        ),
        pt.InnerTxnBuilder.Submit(),
    )




@app.external(authorize=beaker.Authorize.opted_in())
def resolving_order(
    payment1: pt.abi.PaymentTransaction, password: pt.abi.String, lib: pt.abi.Account
) -> pt.Expr:

    shop_fee = pt.ScratchVar(pt.TealType.uint64)
    return pt.Seq(
        pt.Assert(
            pt.And(
                payment1.type_spec().txn_type_enum() == pt.TxnType.Payment,
                payment1.get().receiver() == pt.Global.current_application_address(),
                app.state.hash_pass.get() == pt.Sha256(password.get()),
            )
        ),
        app.state.fee.set(payment1.get().amount()),
        shop_fee.store(app.state.fee.get()),
        transfer_money(shop_fee.load(), pt.Int(1)),
        # transfer_money(shop_fee.load(), library),
    )
