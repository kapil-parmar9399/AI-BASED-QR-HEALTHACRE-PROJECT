import Link from 'next/link';

export default function Navbar() {
    return ( <
        nav style = {
            { padding: '10px', borderBottom: '1px solid #ccc' } } >
        <
        Link href = "/dashboard" > < a style = {
            { marginRight: '10px' } } > Dashboard < /a></Link >
        <
        Link href = "/records" > < a style = {
            { marginRight: '10px' } } > Records < /a></Link >
        <
        Link href = "/qr" > < a style = {
            { marginRight: '10px' } } > QR Scanner < /a></Link >
        <
        /nav>
    );
}